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

import org.dacapo.harness.Callback;
import org.dacapo.harness.CommandLineArgs;

public class DacapoChopinCallback extends Callback {
  static {
    System.loadLibrary("dacapo_callback");
  }

  public DacapoChopinCallback(CommandLineArgs cla) {
    super(cla);
  }

  public void start(String benchmark) {
    if (!isWarmup()) {
      start_native();
    }
    super.start(benchmark);
  };

  public void stop(long duration) {
    super.stop(duration);
    if (!isWarmup()) {
      stop_native();
    }
  }

  public native void start_native();
  public native void stop_native();
}
