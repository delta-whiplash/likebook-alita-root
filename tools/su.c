/*
 * Standalone su binary for Boyue Likebook Alita (K103) / Rockchip RK3368
 * Freestanding ARM64, zero libc dependencies, statically linked.
 *
 * Designed to execute with SetUID permissions (04755) in rootfs (/sbin/su).
 * Avoids any background daemon, localhost network socket, or complex IPC.
 */

#define SYS_read        63
#define SYS_write       64
#define SYS_exit        93
#define SYS_setresgid  149
#define SYS_setresuid  147
#define SYS_setgroups  159
#define SYS_execve     221

static inline long syscall1(long n, long a1) {
    register long x8 __asm__("x8") = n;
    register long x0 __asm__("x0") = a1;
    __asm__ __volatile__("svc #0" : "=r"(x0) : "r"(x8), "r"(x0) : "memory");
    return x0;
}

static inline long syscall3(long n, long a1, long a2, long a3) {
    register long x8 __asm__("x8") = n;
    register long x0 __asm__("x0") = a1;
    register long x1 __asm__("x1") = a2;
    register long x2 __asm__("x2") = a3;
    __asm__ __volatile__("svc #0" : "=r"(x0) : "r"(x8), "r"(x0), "r"(x1), "r"(x2) : "memory");
    return x0;
}

static inline void sys_exit(int code) {
    syscall1(SYS_exit, code);
    while (1) {}
}

static inline int sys_write(int fd, const void *buf, int count) {
    return (int)syscall3(SYS_write, fd, (long)buf, count);
}

static inline int sys_setresuid(int r, int e, int s) {
    return (int)syscall3(SYS_setresuid, r, e, s);
}

static inline int sys_setresgid(int r, int e, int s) {
    return (int)syscall3(SYS_setresgid, r, e, s);
}

static inline int sys_setgroups(int size, const void *list) {
    return (int)syscall3(SYS_setgroups, size, (long)list, 0);
}

static inline int sys_execve(const char *pathname, char *const argv[], char *const envp[]) {
    return (int)syscall3(SYS_execve, (long)pathname, (long)argv, (long)envp);
}

static int str_len(const char *s) {
    int i = 0;
    while (s[i]) i++;
    return i;
}

static int str_eq(const char *a, const char *b) {
    while (*a && (*a == *b)) {
        a++;
        b++;
    }
    return (*a == *b);
}

static void print_str(int fd, const char *s) {
    sys_write(fd, s, str_len(s));
}

void *memcpy(void *dest, const void *src, unsigned long n) {
    char *d = dest;
    const char *s = src;
    while (n--) *d++ = *s++;
    return dest;
}

void *memset(void *s, int c, unsigned long n) {
    char *p = s;
    while (n--) *p++ = (char)c;
    return s;
}

void su_main(int argc, char **argv, char **envp) {
    // Check for standard root-check version flags
    if (argc >= 2) {
        if (str_eq(argv[1], "-v") || str_eq(argv[1], "--version")) {
            print_str(1, "2.82:SUPERSU\n");
            sys_exit(0);
        }
        if (str_eq(argv[1], "-V")) {
            print_str(1, "282\n");
            sys_exit(0);
        }
        if (str_eq(argv[1], "-h") || str_eq(argv[1], "--help")) {
            print_str(1, "Usage: su [-c COMMAND] [-v] [-V]\n");
            sys_exit(0);
        }
    }

    // Elevate to root (UID 0, GID 0, empty supplementary groups)
    sys_setresgid(0, 0, 0);
    sys_setgroups(0, (void*)0);
    sys_setresuid(0, 0, 0);

    const char *sh = "/system/bin/sh";

    char *new_argv[64];
    new_argv[0] = (char*)sh;

    if (argc <= 1) {
        // Interactive shell: su
        new_argv[1] = (char*)0;
    } else if (str_eq(argv[1], "-c")) {
        // su -c command [args...]
        new_argv[1] = "-c";
        int out_idx = 2;
        for (int i = 2; i < argc && out_idx < 62; i++) {
            new_argv[out_idx++] = argv[i];
        }
        new_argv[out_idx] = (char*)0;
    } else {
        // su command [args...]
        new_argv[1] = "-c";
        int out_idx = 2;
        for (int i = 1; i < argc && out_idx < 62; i++) {
            new_argv[out_idx++] = argv[i];
        }
        new_argv[out_idx] = (char*)0;
    }

    sys_execve(sh, new_argv, envp);

    // If execve fails
    print_str(2, "su: execve failed\n");
    sys_exit(1);
}

// ELF naked entry point for aarch64
__attribute__((naked)) void _start(void) {
    __asm__ __volatile__(
        "mov x29, #0\n"
        "mov x30, #0\n"
        "ldr x0, [sp]\n"           // argc
        "add x1, sp, #8\n"          // argv
        "add x2, x1, x0, lsl #3\n"  // skip argv pointers
        "add x2, x2, #8\n"          // envp
        "bl su_main\n"
        "mov x0, #1\n"
        "mov x8, #93\n"
        "svc #0\n"
    );
}
