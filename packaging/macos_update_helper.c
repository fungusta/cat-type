/*
 * Cat Type macOS update helper.
 *
 * Cat Type copies this program out of its bundle and starts it just before it
 * quits. The helper waits for Cat Type to exit, swaps the verified staged
 * bundle into place (atomically when the volume allows it), cleans up, and
 * relaunches Cat Type through LaunchServices. Modelled on Sparkle 2's
 * installer (SUPlainInstaller / SUFileManager).
 *
 * usage: cat-type-update-helper pid installed staged staging_dir lock_dir
 *        helper_dir open_tool gktool swap_mode wait_seconds
 *
 * Exit codes: 0 success, 2 bad arguments, 3 timed out waiting for Cat Type,
 * 4 swap failed and the old app was restored, 5 swap and restore both failed.
 */

#define _DARWIN_C_SOURCE

#include <errno.h>
#include <ftw.h>
#include <libgen.h>
#include <libproc.h>
#include <limits.h>
#include <spawn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/proc_info.h>
#include <sys/stat.h>
#include <sys/sysctl.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <unistd.h>

extern char **environ;

enum {
    EXIT_OK = 0,
    EXIT_USAGE = 2,
    EXIT_TIMEOUT = 3,
    EXIT_RESTORED = 4,
    EXIT_UNRECOVERED = 5,
};

static const char *const STAGING_PREFIX = ".cat-type-update-";
static const char *const HELPER_DIR_PREFIX = "cat-type-update-helper-";
static const char *const LOCK_SUFFIX = ".update-lock";

static void log_message(const char *message, const char *detail) {
    if (detail != NULL) {
        fprintf(stderr, "cat-type-update-helper: %s: %s\n", message, detail);
    } else {
        fprintf(stderr, "cat-type-update-helper: %s\n", message);
    }
}

/* Return 1 and fill *start when pid is a live, non-zombie process. */
static int process_start(pid_t pid, struct timeval *start) {
    struct proc_bsdinfo info;
    int size = proc_pidinfo(pid, PROC_PIDTBSDINFO, 0, &info, sizeof(info));
    if (size != (int)sizeof(info)) {
        return 0;
    }
    if (info.pbi_status == SZOMB) {
        return 0;
    }
    start->tv_sec = (time_t)info.pbi_start_tvsec;
    start->tv_usec = (suseconds_t)info.pbi_start_tvusec;
    return 1;
}

/* Wait for the original process to exit. A reused PID has a new start time. */
static int wait_for_exit(pid_t pid, int wait_seconds) {
    struct timeval original;
    if (!process_start(pid, &original)) {
        return 1;
    }
    long polls = (long)wait_seconds * 20;
    for (long attempt = 0; attempt < polls; attempt++) {
        struct timeval current;
        if (!process_start(pid, &current)) {
            return 1;
        }
        if (current.tv_sec != original.tv_sec
            || current.tv_usec != original.tv_usec) {
            return 1;
        }
        usleep(50 * 1000);
    }
    return 0;
}

static int remove_entry(const char *path, const struct stat *status, int flag,
                        struct FTW *walk) {
    (void)status;
    (void)flag;
    (void)walk;
    if (remove(path) != 0 && errno != ENOENT) {
        log_message("could not remove", path);
    }
    return 0;
}

static void remove_tree(const char *path) {
    struct stat status;
    if (lstat(path, &status) != 0) {
        return;
    }
    nftw(path, remove_entry, 16, FTW_DEPTH | FTW_PHYS);
}

static int run_and_wait(const char *tool, char *const argv[]) {
    pid_t child;
    if (posix_spawn(&child, tool, NULL, NULL, argv, environ) != 0) {
        log_message("could not start", tool);
        return -1;
    }
    int status = 0;
    while (waitpid(child, &status, 0) < 0) {
        if (errno != EINTR) {
            return -1;
        }
    }
    return status;
}

static int macos_at_least(int major, int minor) {
    char version[32] = {0};
    size_t size = sizeof(version) - 1;
    if (sysctlbyname("kern.osproductversion", version, &size, NULL, 0) != 0) {
        return 0;
    }
    int found_major = 0;
    int found_minor = 0;
    if (sscanf(version, "%d.%d", &found_major, &found_minor) < 1) {
        return 0;
    }
    return found_major > major || (found_major == major && found_minor >= minor);
}

static void relaunch(const char *open_tool, const char *bundle) {
    char *argv[] = {(char *)open_tool, (char *)bundle, NULL};
    run_and_wait(open_tool, argv);
}

static void cleanup(const char *staging_dir, const char *lock_dir,
                    const char *helper_dir) {
    remove_tree(staging_dir);
    remove_tree(lock_dir);
    remove_tree(helper_dir);
}

static int has_prefix(const char *value, const char *prefix) {
    return strncmp(value, prefix, strlen(prefix)) == 0;
}

/* Copy dirname/basename results, since both may reuse static storage. */
static int path_parts(const char *path, char *parent, char *name) {
    char buffer[PATH_MAX];
    if (strlcpy(buffer, path, sizeof(buffer)) >= sizeof(buffer)) {
        return 0;
    }
    if (strlcpy(parent, dirname(buffer), PATH_MAX) >= PATH_MAX) {
        return 0;
    }
    if (strlcpy(buffer, path, sizeof(buffer)) >= sizeof(buffer)) {
        return 0;
    }
    return strlcpy(name, basename(buffer), PATH_MAX) < PATH_MAX;
}

/* Refuse to touch anything outside the layout Cat Type creates. */
static int layout_is_expected(const char *installed, const char *staged,
                              const char *staging_dir, const char *lock_dir,
                              const char *helper_dir) {
    char installed_parent[PATH_MAX], installed_name[PATH_MAX];
    char staged_parent[PATH_MAX], staged_name[PATH_MAX];
    char staging_parent[PATH_MAX], staging_name[PATH_MAX];
    char helper_parent[PATH_MAX], helper_name[PATH_MAX];
    char expected_lock[PATH_MAX];

    if (!path_parts(installed, installed_parent, installed_name)
        || !path_parts(staged, staged_parent, staged_name)
        || !path_parts(staging_dir, staging_parent, staging_name)
        || !path_parts(helper_dir, helper_parent, helper_name)) {
        return 0;
    }
    if (installed[0] != '/' || strcmp(staged_parent, staging_dir) != 0
        || strcmp(staging_parent, installed_parent) != 0
        || strcmp(staged_name, installed_name) != 0
        || !has_prefix(staging_name, STAGING_PREFIX)
        || !has_prefix(helper_name, HELPER_DIR_PREFIX)) {
        return 0;
    }
    if (snprintf(expected_lock, sizeof(expected_lock), "%s%s", installed,
                 LOCK_SUFFIX) >= (int)sizeof(expected_lock)) {
        return 0;
    }
    return strcmp(expected_lock, lock_dir) == 0;
}

int main(int argc, char *argv[]) {
    if (argc != 11) {
        fprintf(stderr,
                "usage: cat-type-update-helper pid installed staged staging_dir "
                "lock_dir helper_dir open_tool gktool swap_mode wait_seconds\n");
        return EXIT_USAGE;
    }
    char *end = NULL;
    long pid_value = strtol(argv[1], &end, 10);
    if (*argv[1] == '\0' || *end != '\0' || pid_value <= 0 || pid_value > INT_MAX) {
        log_message("invalid pid", argv[1]);
        return EXIT_USAGE;
    }
    const char *installed = argv[2];
    const char *staged = argv[3];
    const char *staging_dir = argv[4];
    const char *lock_dir = argv[5];
    const char *helper_dir = argv[6];
    const char *open_tool = argv[7];
    const char *gktool = argv[8];
    const char *swap_mode = argv[9];
    long wait_seconds = strtol(argv[10], &end, 10);
    if (*argv[10] == '\0' || *end != '\0' || wait_seconds < 1 || wait_seconds > 300) {
        log_message("invalid wait_seconds", argv[10]);
        return EXIT_USAGE;
    }
    int use_swap = strcmp(swap_mode, "swap") == 0;
    if (!use_swap && strcmp(swap_mode, "move") != 0) {
        log_message("invalid swap_mode", swap_mode);
        return EXIT_USAGE;
    }
    if (!layout_is_expected(installed, staged, staging_dir, lock_dir, helper_dir)) {
        log_message("unexpected update layout", installed);
        return EXIT_USAGE;
    }

    if (!wait_for_exit((pid_t)pid_value, (int)wait_seconds)) {
        log_message("timed out waiting for Cat Type to quit", NULL);
        cleanup(staging_dir, lock_dir, helper_dir);
        return EXIT_TIMEOUT;
    }

    int installed_new = 0;
    if (use_swap) {
        if (renamex_np(staged, installed, RENAME_SWAP) == 0) {
            installed_new = 1;
        } else {
            log_message("atomic swap failed, falling back", strerror(errno));
        }
    }
    if (!installed_new) {
        char old_bundle[PATH_MAX];
        if (snprintf(old_bundle, sizeof(old_bundle), "%s/old.app", staging_dir)
            >= (int)sizeof(old_bundle)) {
            log_message("path too long", staging_dir);
            cleanup(staging_dir, lock_dir, helper_dir);
            relaunch(open_tool, installed);
            return EXIT_RESTORED;
        }
        if (rename(installed, old_bundle) != 0) {
            log_message("could not move the old app aside", strerror(errno));
            cleanup(staging_dir, lock_dir, helper_dir);
            relaunch(open_tool, installed);
            return EXIT_RESTORED;
        }
        if (rename(staged, installed) != 0) {
            log_message("could not move the new app into place", strerror(errno));
            if (rename(old_bundle, installed) != 0) {
                log_message("could not restore the old app", strerror(errno));
                remove_tree(lock_dir);
                remove_tree(helper_dir);
                return EXIT_UNRECOVERED;
            }
            cleanup(staging_dir, lock_dir, helper_dir);
            relaunch(open_tool, installed);
            return EXIT_RESTORED;
        }
    }

    if (utimes(installed, NULL) != 0) {
        log_message("could not update the app's modification time", strerror(errno));
    }
    if (strcmp(gktool, "-") != 0 && macos_at_least(14, 4)) {
        char *scan_argv[] = {(char *)gktool, "scan", (char *)installed, NULL};
        run_and_wait(gktool, scan_argv);
    }
    cleanup(staging_dir, lock_dir, helper_dir);
    relaunch(open_tool, installed);
    return EXIT_OK;
}
