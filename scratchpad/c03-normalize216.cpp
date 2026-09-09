#include "sherpa-onnx/csrc/math.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <vector>
int main() {
    std::vector<float> near(2000);
    for (int i = 0; i < 1000; ++i) {
        near[2 * i] = -15.94f;
        near[2 * i + 1] = float(i % 7);
    }
    near[1000] += .075f;
    sherpa_onnx::NemoNormalizePerFeature(near.data(), 1000, 2);
    double maximum = 0;
    for (int i = 0; i < 1000; ++i) {
        if (!std::isfinite(near[2 * i])) return 2;
        maximum = std::max(maximum, double(std::fabs(near[2 * i])));
    }
    std::vector<float> constant(8, 3.5f);
    sherpa_onnx::NemoNormalizePerFeature(constant.data(), 8, 1);
    double constant_max = 0;
    for (float value : constant) {
        if (!std::isfinite(value)) return 3;
        constant_max = std::max(constant_max, double(std::fabs(value)));
    }
    std::printf("{\"nearConstantMax\":%.9g,\"constantMax\":%.9g}\n", maximum, constant_max);
    return 0;
}
