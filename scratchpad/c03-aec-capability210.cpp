#include <windows.h>
#include <mmdeviceapi.h>
#include <audioclient.h>
#include <wrl/client.h>
#include <cstdio>
#include <stdexcept>
using Microsoft::WRL::ComPtr;

static void check(HRESULT hr) { if (FAILED(hr)) throw hr; }
static void probe(IMMDeviceEnumerator* enumerator, ERole role, AUDIO_STREAM_CATEGORY category) {
    printf("{\"role\":%d,\"category\":%d", int(role), int(category));
    try {
        ComPtr<IMMDevice> device;
        check(enumerator->GetDefaultAudioEndpoint(eCapture, role, &device));
        LPWSTR id = nullptr;
        check(device->GetId(&id));
        printf(",\"endpointId\":\"%ls\"", id);
        CoTaskMemFree(id);
        ComPtr<IAudioClient2> client;
        check(device->Activate(__uuidof(IAudioClient2), CLSCTX_INPROC_SERVER, nullptr,
                              reinterpret_cast<void**>(client.GetAddressOf())));
        AudioClientProperties props = {};
        props.cbSize = sizeof(props);
        props.eCategory = category;
        props.Options = AUDCLNT_STREAMOPTIONS_RAW;
        check(client->SetClientProperties(&props));
        WAVEFORMATEX* format = nullptr;
        check(client->GetMixFormat(&format));
        printf(",\"sampleRate\":%lu,\"channels\":%u", format->nSamplesPerSec, format->nChannels);
        const HRESULT initialized = client->Initialize(AUDCLNT_SHAREMODE_SHARED,
            AUDCLNT_STREAMFLAGS_EVENTCALLBACK, 10000000, 0, format, nullptr);
        CoTaskMemFree(format);
        check(initialized);
        ComPtr<IAudioEffectsManager> effectsManager;
        const HRESULT effectsHr = client->GetService(IID_PPV_ARGS(&effectsManager));
        printf(",\"effectsServiceHr\":\"%08lx\"", static_cast<unsigned long>(effectsHr));
        if (SUCCEEDED(effectsHr)) {
            AUDIO_EFFECT* effects = nullptr;
            UINT32 count = 0;
            check(effectsManager->GetAudioEffects(&effects, &count));
            printf(",\"effects\":[");
            for (UINT32 i = 0; i < count; ++i) {
                wchar_t guid[40] = {};
                StringFromGUID2(effects[i].id, guid, 40);
                printf("%s{\"id\":\"%ls\",\"state\":%d,\"canSetState\":%s}",
                    i ? "," : "", guid, int(effects[i].state), effects[i].canSetState ? "true" : "false");
            }
            CoTaskMemFree(effects);
            printf("]");
        }
        ComPtr<IAcousticEchoCancellationControl> control;
        const HRESULT controlHr = client->GetService(IID_PPV_ARGS(&control));
        printf(",\"aecControlServiceHr\":\"%08lx\",\"initialized\":true,\"started\":false}",
               static_cast<unsigned long>(controlHr));
    } catch (HRESULT hr) {
        printf(",\"errorHr\":\"%08lx\",\"started\":false}", static_cast<unsigned long>(hr));
    }
    printf("\n");
}
int main() {
    HRESULT hr = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
    if (FAILED(hr)) return 2;
    int result = 0;
    try {
        ComPtr<IMMDeviceEnumerator> enumerator;
        check(CoCreateInstance(__uuidof(MMDeviceEnumerator), nullptr, CLSCTX_ALL,
                               IID_PPV_ARGS(&enumerator)));
        for (ERole role : {eConsole, eMultimedia, eCommunications}) {
            probe(enumerator.Get(), role, AudioCategory_Other);
            probe(enumerator.Get(), role, AudioCategory_Communications);
        }
    } catch (HRESULT) { result = 3; }
    CoUninitialize();
    return result;
}
