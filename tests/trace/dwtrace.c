/* Linux LD_PRELOAD tracer for the durablewrite ground-truth tests.
 *
 * Logs the file system calls a process makes inside DWTRACE_DIR, one per
 * line, to DWTRACE_OUT, and can kill the process with SIGKILL right before or
 * right after the Nth logged call (DWTRACE_KILL_BEFORE / DWTRACE_KILL_AFTER),
 * which stops it at a real system call boundary with no cleanup at all.
 *
 * Build: gcc -shared -fPIC -O1 -o dwtrace.so dwtrace.c -ldl
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <signal.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define MAX_FDS 4096
static char *names[MAX_FDS];
static int count;

static const char *root(void) { return getenv("DWTRACE_DIR"); }

static const char *inside(const char *path) {
    const char *dir = root();
    size_t n;
    if (!dir || !path) return NULL;
    n = strlen(dir);
    if (strncmp(path, dir, n) != 0) return NULL;
    if (path[n] == '\0') return ".";
    if (path[n] != '/') return NULL;
    return path + n + 1;
}

static int limit(const char *name) {
    const char *v = getenv(name);
    return v ? atoi(v) : 0;
}

static void emit(const char *fmt, ...) {
    char line[1024];
    va_list ap;
    const char *out = getenv("DWTRACE_OUT");
    count++;
    if (count == limit("DWTRACE_KILL_BEFORE")) raise(SIGKILL);
    if (out) {
        int fd;
        int (*real_open)(const char *, int, ...) = dlsym(RTLD_NEXT, "open");
        va_start(ap, fmt);
        vsnprintf(line, sizeof line - 1, fmt, ap);
        va_end(ap);
        strcat(line, "\n");
        fd = real_open(out, O_WRONLY | O_APPEND | O_CREAT | O_CLOEXEC, 0600);
        if (fd >= 0) {
            ssize_t ignored = write(fd, line, strlen(line));
            (void)ignored;
            close(fd);
        }
    }
}

static void after(void) {
    if (count == limit("DWTRACE_KILL_AFTER")) raise(SIGKILL);
}

static const char *fd_name(int fd) { return (fd >= 0 && fd < MAX_FDS) ? names[fd] : NULL; }

static int opened(const char *path, int flags, int fd) {
    const char *rel = inside(path);
    if (fd >= 0 && fd < MAX_FDS && rel) {
        free(names[fd]);
        names[fd] = strdup(rel);
        emit("open %s%s%s", rel, (flags & O_EXCL) ? " excl" : "",
             (flags & O_DIRECTORY) ? " dir" : "");
        after();
    }
    return fd;
}

#define OPEN_MODE(flags) \
    mode_t mode = 0; \
    if ((flags) & (O_CREAT | O_TMPFILE)) { va_list ap; va_start(ap, flags); \
        mode = va_arg(ap, mode_t); va_end(ap); }

int open(const char *path, int flags, ...) {
    OPEN_MODE(flags)
    int (*real)(const char *, int, ...) = dlsym(RTLD_NEXT, "open");
    return opened(path, flags, real(path, flags, mode));
}

int open64(const char *path, int flags, ...) {
    OPEN_MODE(flags)
    int (*real)(const char *, int, ...) = dlsym(RTLD_NEXT, "open64");
    return opened(path, flags, real(path, flags, mode));
}

int openat(int dirfd, const char *path, int flags, ...) {
    OPEN_MODE(flags)
    int (*real)(int, const char *, int, ...) = dlsym(RTLD_NEXT, "openat");
    return opened(path, flags, real(dirfd, path, flags, mode));
}

int openat64(int dirfd, const char *path, int flags, ...) {
    OPEN_MODE(flags)
    int (*real)(int, const char *, int, ...) = dlsym(RTLD_NEXT, "openat64");
    return opened(path, flags, real(dirfd, path, flags, mode));
}

ssize_t write(int fd, const void *buf, size_t n) {
    ssize_t (*real)(int, const void *, size_t) = dlsym(RTLD_NEXT, "write");
    const char *name = fd_name(fd);
    ssize_t result;
    if (name) emit("write %s", name);
    result = real(fd, buf, n);
    if (name) after();
    return result;
}

#define FD_CALL(fn, label) \
    int fn(int fd) { \
        int (*real)(int) = dlsym(RTLD_NEXT, #fn); \
        const char *name = fd_name(fd); \
        int result; \
        if (name) emit(label " %s", name); \
        result = real(fd); \
        if (name) after(); \
        return result; \
    }

FD_CALL(fsync, "fsync")
FD_CALL(fdatasync, "fdatasync")

int close(int fd) {
    int (*real)(int) = dlsym(RTLD_NEXT, "close");
    if (fd >= 0 && fd < MAX_FDS && names[fd]) {
        free(names[fd]);
        names[fd] = NULL;
    }
    return real(fd);
}

#define TWO_PATHS(label, call) \
    const char *a = inside(old), *b = inside(new); \
    int result; \
    if (a || b) emit(label " %s %s", a ? a : "?", b ? b : "?"); \
    result = call; \
    if (a || b) after(); \
    return result;

int rename(const char *old, const char *new) {
    int (*real)(const char *, const char *) = dlsym(RTLD_NEXT, "rename");
    TWO_PATHS("rename", real(old, new))
}

int renameat(int od, const char *old, int nd, const char *new) {
    int (*real)(int, const char *, int, const char *) = dlsym(RTLD_NEXT, "renameat");
    TWO_PATHS("rename", real(od, old, nd, new))
}

int link(const char *old, const char *new) {
    int (*real)(const char *, const char *) = dlsym(RTLD_NEXT, "link");
    TWO_PATHS("link", real(old, new))
}

int linkat(int od, const char *old, int nd, const char *new, int flags) {
    int (*real)(int, const char *, int, const char *, int) = dlsym(RTLD_NEXT, "linkat");
    TWO_PATHS("link", real(od, old, nd, new, flags))
}

int unlink(const char *path) {
    int (*real)(const char *) = dlsym(RTLD_NEXT, "unlink");
    const char *rel = inside(path);
    int result;
    if (rel) emit("unlink %s", rel);
    result = real(path);
    if (rel) after();
    return result;
}
