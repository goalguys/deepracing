#ifndef TIMESTAMPED_CAR_DATA_H
#define  TIMESTAMPED_CAR_DATA_H


#include "car_data/car_data.h"
#include <chrono>
namespace deepf1
{
	struct timestamped_udp_data {
		UDPPacket data;
		std::chrono::high_resolution_clock::time_point timestamp;
	}; 
	typedef struct timestamped_udp_data TimestampedUDPData;
}

#endif
