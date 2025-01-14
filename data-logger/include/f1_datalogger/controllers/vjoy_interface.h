#ifndef INCLUDE_CONTROLLERS_VJOY_INTERFACE_H_
#define INCLUDE_CONTROLLERS_VJOY_INTERFACE_H_
#include <cmath>
#include <f1_datalogger/controllers/f1_interface.h>
#include <vJoy_plusplus/vjoy.h>
#include <mutex>

namespace deepf1 {
	
	class F1_DATALOGGER_CONTROLS_PUBLIC VJoyInterface : public F1Interface
	{
	public:
		VJoyInterface(const unsigned int& device_id = 1);
		virtual ~VJoyInterface();
		void setCommands(const F1ControlCommand& command) override;
		void pushDRS() override;
		void setButtons(long bitmask);
	  	void setStateDirectly(const XINPUT_STATE& gamepad_state) override;
	  	XINPUT_STATE getCurrentState() override;
	private:
		vjoy_plusplus::vJoy vjoy_;
		double max_vjoysteer_, max_vjoythrottle_ , max_vjoybrake_;
		vjoy_plusplus::JoystickPosition current_js;
		std::mutex mutex_;
	};
	
}
#endif
