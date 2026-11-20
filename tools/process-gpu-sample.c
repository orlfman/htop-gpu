/*
Exercise htop's process GPU accounting for fixture PID 100, one refresh per input line.
With a second argument "intel", the Intel meters sample in the same refresh first, as in htop.
Each line also reports how often this refresh opened the mount table.
*/

#include "config.h" // IWYU pragma: keep

#include <fcntl.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "CRT.h"
#include "linux/Compat.h"
#include "linux/GPU.h"
#include "linux/IntelGPU.h"
#include "linux/LinuxMachine.h"
#include "linux/LinuxProcess.h"
#include "linux/LinuxProcessTable.h"


static unsigned mountTableOpens;

FILE* __real_fopen(const char* path, const char* mode);
FILE* __wrap_fopen(const char* path, const char* mode);
FILE* __wrap_fopen(const char* path, const char* mode) {
   if (strstr(path, "/self/mountinfo"))
      mountTableOpens++;
   return __real_fopen(path, mode);
}

void CRT_done(void) {
}

int main(int argc, char** argv) {
   if (argc != 2 && argc != 3)
      return 1;
   bool intel = argc == 3 && strcmp(argv[2], "intel") == 0;

   LinuxMachine machine = {0};
   LinuxProcessTable table = { .super.super.host = &machine.super };
   LinuxProcess process = { .super.super.host = &machine.super, .super.super.id = 100 };
#ifdef HAVE_OPENAT
   openat_arg_t procFd = open(argv[1], O_DIRECTORY | O_RDONLY);
   if (procFd < 0)
      return 1;
#else
   openat_arg_t procFd = argv[1];
#endif
   char line[64];
   while (fgets(line, sizeof(line), stdin)) {
      machine.super.prevMonotonicMs = machine.super.monotonicMs;
      machine.super.monotonicMs = strtoull(line, NULL, 10);
      mountTableOpens = 0;
      if (intel)
         IntelGPU_getSample(machine.super.monotonicMs);
      GPU_readProcessData(&table, &process, procFd);
      printf("{\"time\":%llu,\"percent\":%.2f,\"mountinfo\":%u}\n", process.gpu_time, (double)process.gpu_percent, mountTableOpens);
      fflush(stdout);
   }

   Compat_openatArgClose(procFd);
   while (machine.gpuEngineData) {
      GPUEngineData* engine = machine.gpuEngineData;
      machine.gpuEngineData = engine->next;
      free(engine->key);
      free(engine);
   }
   return 0;
}
