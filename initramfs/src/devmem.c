#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stdint.h>
int main(int c,char**v){ if(c<2){fprintf(stderr,"devmem ADDR [VALUE]\n");return 1;}
 uint64_t a=strtoull(v[1],0,0); int fd=open("/dev/mem",O_RDWR|O_SYNC); if(fd<0){perror("open");return 1;}
 long ps=sysconf(_SC_PAGESIZE); volatile uint8_t*m=mmap(0,ps,PROT_READ|PROT_WRITE,MAP_SHARED,fd,a&~(ps-1)); if(m==MAP_FAILED){perror("mmap");return 1;}
 volatile uint32_t*r=(volatile uint32_t*)(m+(a&(ps-1))); if(c>2)*r=(uint32_t)strtoul(v[2],0,0); printf("0x%08x\n",*r); return 0;}
