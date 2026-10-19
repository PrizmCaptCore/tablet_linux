#include <unistd.h>
#include <sys/syscall.h>
#include <linux/reboot.h>
int main(int c, char **v) { sync(); return syscall(SYS_reboot, LINUX_REBOOT_MAGIC1, LINUX_REBOOT_MAGIC2, LINUX_REBOOT_CMD_RESTART2, c > 1 ? v[1] : "bootloader"); }
