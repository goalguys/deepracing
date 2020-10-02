#include "App.h"
#include "SampleWindow.h"
#include <iostream>
#include <f1_datalogger/car_data/timestamped_image_data.h>
#include <opencv2/highgui.hpp>
#include <opencv2/imgproc.hpp>

namespace winrt
{
    using namespace Windows::Storage::Pickers;
    using namespace Windows::Graphics::Capture;
    using namespace Windows::UI::Composition;
}

namespace util
{
    using namespace desktop;
}

int __stdcall WinMain(HINSTANCE instance, HINSTANCE, PSTR cmdLine, int cmdShow)
{
    // SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2); // works but everything draws small
    // Initialize COM
    winrt::init_apartment(winrt::apartment_type::multi_threaded);
    std::cout<<"Hello World"<<std::endl;
    MessageBoxW(nullptr,
            L"Hello World!",
            L"Win32CaptureSample",
        MB_OK | MB_ICONINFORMATION);

    // Check to see that capture is supported
    auto isCaptureSupported = winrt::Windows::Graphics::Capture::GraphicsCaptureSession::IsSupported();
    if (!isCaptureSupported)
    {
        MessageBoxW(nullptr,
            L"Screen capture is not supported on this device for this release of Windows!",
            L"Win32CaptureSample",
            MB_OK | MB_ICONERROR);
        return 1;
    }

    SampleWindow::RegisterWindowClass();

    // Create the DispatcherQueue that the compositor needs to run
    auto controller = util::CreateDispatcherQueueControllerForCurrentThread();

    // Initialize Composition
    // auto compositor = winrt::Compositor();
    // auto root = compositor.CreateContainerVisual();
    // root.RelativeSizeAdjustment({ 1.0f, 1.0f });
    // root.Size({ -220.0f, 0.0f });
    // root.Offset({ 220.0f, 0.0f, 0.0f });

    // Create the app
    auto app = std::make_shared<App>();

    auto window = SampleWindow(instance, cmdShow, app);
    // Message pump
    MSG msg;
    while (GetMessageW(&msg, nullptr, 0, 0))
    {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
        if (!(app->m_capture))
        {
            continue;
        }
        deepf1::TimestampedImageData curr_image = app->m_capture->getData();
        if (!curr_image.image.empty())
        {
         
            cv::putText(curr_image.image, std::string("Image Type: ") + cv::typeToString(curr_image.image.type()), cv::Point(curr_image.image.cols / 2-75, curr_image.image.rows / 2),
            cv::FONT_HERSHEY_DUPLEX,
            1.0,
            cv::Scalar(0, 0, 0));  
            cv::imshow("CapWin", curr_image.image);
            cv::waitKey(1);
        }
    }

    MessageBoxW(nullptr,
            L"Goodbye World!",
            L"Win32CaptureSample",
        MB_OK | MB_ICONINFORMATION);
    return static_cast<int>(msg.wParam);
}