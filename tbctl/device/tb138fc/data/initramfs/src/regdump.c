// regdump NAME:BASE:LEN ... - print 32-bit MMIO registers as "NAME+0xOFF 0xVALUE" (for diffing)
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

int main(int argc, char **argv)
{
	int fd = open("/dev/mem", O_RDONLY | O_SYNC);
	long ps = sysconf(_SC_PAGESIZE);

	if (fd < 0) {
		perror("open /dev/mem");
		return 1;
	}
	for (int i = 1; i < argc; i++) {
		char name[64];
		unsigned long base, len;

		if (sscanf(argv[i], "%63[^:]:%lx:%lx", name, &base, &len) != 3) {
			fprintf(stderr, "bad spec %s\n", argv[i]);
			return 1;
		}
		unsigned long start = base & ~(ps - 1);
		size_t map = (base - start + len + ps - 1) & ~(ps - 1);
		volatile uint8_t *m = mmap(NULL, map, PROT_READ, MAP_SHARED, fd, start);

		if (m == MAP_FAILED) {
			perror(name);
			continue;
		}
		for (unsigned long off = 0; off < len; off += 4)
			printf("%s+0x%03lx 0x%08x\n", name, off,
			       *(volatile uint32_t *)(m + (base - start) + off));
		munmap((void *)m, map);
	}
	return 0;
}
