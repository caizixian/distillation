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

import dacapo.Callback;

public class Dacapo2006Callback extends Callback {
  static {
    System.loadLibrary("dacapo_callback");
  }

  public Dacapo2006Callback() {
    super();
  }

  public void startWarmup(String benchmark) {
    super.startWarmup(benchmark);
  };

  public void stopWarmup() {
    super.stopWarmup();
  }
  public void start(String benchmark) {
    start_native();
    super.start(benchmark);
  };

  public void stop() {
    super.stop();
    stop_native();
  }

  public native void start_native();
  public native void stop_native();
}
