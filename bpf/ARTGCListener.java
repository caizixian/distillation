/*
 * Copyright (C) 2022 Google
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

// Put the file under /platform_testing/libraries/device-collectors/src/main/java/android/device/collectors/ARTGCListener.java

// make PlatformScenarioTests
// adb install -g $ANDROID_PRODUCT_OUT/testcases/PlatformScenarioTests/arm64/PlatformScenarioTests.apk
// adb shell am instrument -w -r -e class android.platform.helpers.external.clock.ClockAppTest  -e listener android.device.collectors.ARTGCListener -e process-names com.google.android.deskclock -e skip_test_failure_metrics true android.platform.test.scenario/androidx.test.runner.AndroidJUnitRunne
package android.device.collectors;

import android.device.collectors.annotations.OptionClass;
import android.os.Bundle;

import androidx.annotation.VisibleForTesting;

import android.os.SystemClock;
import android.util.Log;

import androidx.test.InstrumentationRegistry;
import androidx.test.uiautomator.UiDevice;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.io.File;
import java.io.FileNotFoundException;
import java.util.Scanner;
import java.math.BigInteger;


import com.android.helpers.ICollectorHelper;

class ARTGCHelper implements ICollectorHelper<BigInteger> {
    private static final String LOG_TAG = ARTGCHelper.class.getSimpleName();
    private UiDevice mDevice;
    private int pid = 0;
    
    @Override
    public boolean startCollecting() {
        Log.i(LOG_TAG, "XXXXX startCollecting");
        try {
            String output;
            output = getDevice().executeShellCommand("pidof python3").trim();
            if (output.length() > 0) {
                Log.e(LOG_TAG, "Didn't start collecting. Exisiting python3 detected");
                return false;
            }
            getDevice().executeShellCommand("sh /data/local/run_art_gc.sh");
            int attempts = 0;
            do {
                output = getDevice().executeShellCommand("pidof python3").trim();
                attempts++;
            } while (output.length() == 0 && attempts < 42);
            if (output.length() > 0) {
                pid = Integer.parseInt(output);
                Log.i(LOG_TAG, String.format("Started art_gc.py pid %d", pid));
                return true;
            } else {
                Log.e(LOG_TAG, "Failed to get python3 pid");
                return false;
            }
        } catch (Exception e) {
            Log.e(LOG_TAG, String.format("Failed to start art_gc.py %s", e.toString()));
            return false;
        }
    }

    @Override
    public Map<String, BigInteger> getMetrics() {
        Log.i(LOG_TAG, "XXXXX getMetrics");
        killARTGC();
        Map<String, BigInteger> result = new HashMap<>();
        if (pid == 0) {
            Log.e(LOG_TAG, "No metrics. pid of python3 not found");
            return result;
        }
        try {
            File fd = new File("/data/local/latest.out");
            Scanner s = new Scanner(fd);
            while (s.hasNextLine()) {
                String line = s.nextLine().trim();
                String[] parts = line.split(",");
                result.put(parts[0], new BigInteger(parts[1]));
            }
            s.close();
        } catch (Exception e) {
            Log.e(LOG_TAG, String.format("Failed to getMetrics %s", e.toString()));
        }
        return result;
    }

    private void killARTGC() {
        try {
            if (pid == 0) {
                Log.e(LOG_TAG, "art_gc.py didn't start");
            } else {
                getDevice().executeShellCommand(String.format("su root kill %d", pid));
                Log.i(LOG_TAG, String.format("Killed art_gc.py pid %d", pid));
            }
        } catch (Exception e) {
            Log.e(LOG_TAG, String.format("Failed to kill art_gc.py %s", e.toString()));
        }
    }

    @Override
    public boolean stopCollecting() {
        Log.i(LOG_TAG, "XXXXX stopCollecting");
        return true;
    }
    
    private UiDevice getDevice() {
        if (mDevice == null) {
            mDevice = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation());
        }
        return mDevice;
    }
}


@OptionClass(alias = "art-gc-collector")
public class ARTGCListener extends BaseCollectionListener<Integer> {
    private ARTGCHelper mARTGCHelper = new ARTGCHelper();

    public ARTGCListener() {
        createHelperInstance(mARTGCHelper);
    }
}
