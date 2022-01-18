// Copyright 2021 Zixian Cai
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include <jni.h>
#include <stdio.h>
#include <dlfcn.h>

JNIEXPORT void JNICALL Java_Dacapo2006Callback_start_1native
  (JNIEnv *env, jobject o) {
  void* handle = dlopen(NULL, RTLD_LAZY);
  void (*harness_begin)() = dlsym(handle, "harness_begin");
  if (harness_begin != NULL)
      (*harness_begin)();
}

JNIEXPORT void JNICALL Java_Dacapo2006Callback_stop_1native
  (JNIEnv *env, jobject o) {
  void* handle = dlopen(NULL, RTLD_LAZY);
  void (*harness_end)() = dlsym(handle, "harness_end");
  if (harness_end != NULL)
    (*harness_end)();
}

JNIEXPORT void JNICALL Java_DacapoBachCallback_start_1native
  (JNIEnv *env, jobject o) {
  void* handle = dlopen(NULL, RTLD_LAZY);
  void (*harness_begin)() = dlsym(handle, "harness_begin");
  if (harness_begin != NULL)
    (*harness_begin)();
}

JNIEXPORT void JNICALL Java_DacapoBachCallback_stop_1native
  (JNIEnv *env, jobject o) {
  void* handle = dlopen(NULL, RTLD_LAZY);
  void (*harness_end)() = dlsym(handle, "harness_end");
  if (harness_end != NULL)
    (*harness_end)();
}
