
set(${PROJECT_NAME}_generate_vjoy_calibration_srcfile generate_vjoy_calibration.cpp)
set(${PROJECT_NAME}_test_vjoy_calibration_srcfile test_vjoy_calibration.cpp)


add_executable(${PROJECT_NAME}_cv_viewer_example
cv_viewer.cpp
)
target_link_libraries(${PROJECT_NAME}_cv_viewer_example
${PROJECT_NAME}
${PROJECT_NAME}_eigen_utils
${PROJECT_NAME}_image_logging
${PROJECT_NAME}_image_logging_common
${PROJECT_NAME}_proto
${PROJECT_NAME}_udp_logging
${PROJECT_NAME}_udp_logging_common
${screen_capture_lite_LIBRARIES}
${screen_capture_lite_PLATFORM_LIBS}
${Boost_TARGETS}
${TBB_IMPORTED_TARGETS}
Eigen3::Eigen
)


add_executable(${PROJECT_NAME}_proto_rebroadcaster
proto_rebroadcaster.cpp
)
target_link_libraries(${PROJECT_NAME}_proto_rebroadcaster
    ${PROJECT_NAME}
    ${PROJECT_NAME}_image_logging
	${PROJECT_NAME}_image_logging_common
	${PROJECT_NAME}_image_utils
	${PROJECT_NAME}_proto
    ${PROJECT_NAME}_udp_logging
    ${PROJECT_NAME}_udp_logging_common
    ${Boost_TARGETS}
	${screen_capture_lite_LIBRARIES}
	${screen_capture_lite_PLATFORM_LIBS}
)

set(install_targets
#executables.
${PROJECT_NAME}_proto_rebroadcaster
${PROJECT_NAME}_cv_viewer_example
)

if(MSVC AND BUILD_CONTROLLERS)
	#find_package(vJoy_plusplus REQUIRED)
	set(WITH_VJOY ON)
	add_executable(${PROJECT_NAME}_generate_vjoy_calibration
	${${PROJECT_NAME}_generate_vjoy_calibration_srcfile}
	)
	target_link_libraries(${PROJECT_NAME}_generate_vjoy_calibration
		${PROJECT_NAME}
		${PROJECT_NAME}_image_logging
		${PROJECT_NAME}_image_logging_common
		${PROJECT_NAME}_udp_logging
		${PROJECT_NAME}_udp_logging_common
		${Boost_TARGETS}
		${screen_capture_lite_LIBRARIES}
		${screen_capture_lite_PLATFORM_LIBS}
		${PROJECT_NAME}_controllers
		vjoy::vJoy_plusplus
	)
	add_executable(${PROJECT_NAME}_test_vjoy_calibration
	${${PROJECT_NAME}_test_vjoy_calibration_srcfile}
	)
	target_link_libraries(${PROJECT_NAME}_test_vjoy_calibration
		${PROJECT_NAME}
		${PROJECT_NAME}_controllers
		${PROJECT_NAME}_image_logging
		${PROJECT_NAME}_image_logging_common
		${PROJECT_NAME}_udp_logging
		${PROJECT_NAME}_udp_logging_common
		${Boost_TARGETS}
		${screen_capture_lite_LIBRARIES}
		${screen_capture_lite_PLATFORM_LIBS}
		vjoy::vJoy_plusplus
	)
		
	add_executable(${PROJECT_NAME}_test_vjoy_lag
	  test_vjoy_lag.cpp
	)
	target_link_libraries(${PROJECT_NAME}_test_vjoy_lag
		${PROJECT_NAME}
		${PROJECT_NAME}_image_logging
		${PROJECT_NAME}_image_logging_common
		${PROJECT_NAME}_image_utils
		${PROJECT_NAME}_proto
		${PROJECT_NAME}_udp_logging
		${PROJECT_NAME}_udp_logging_common
		${Boost_TARGETS}
		${screen_capture_lite_LIBRARIES}
		${screen_capture_lite_PLATFORM_LIBS}
		${TBB_IMPORTED_TARGETS} 
		vjoy::vJoy_plusplus
		${YAML_CPP_LIBRARIES}
		yaml-cpp
	)
	if(YAML_CPP_DLL)
		target_compile_definitions(${PROJECT_NAME}_test_vjoy_lag PRIVATE "YAML_CPP_DLL")
	endif()
	list(APPEND install_targets ${PROJECT_NAME}_test_vjoy_calibration ${PROJECT_NAME}_generate_vjoy_calibration ${PROJECT_NAME}_test_vjoy_lag)
else()
	set(WITH_VJOY OFF)
endif()


option(BUILD_MULTITHREADED_EXAMPLE "" ON)
if(BUILD_MULTITHREADED_EXAMPLE)
	add_executable(${PROJECT_NAME}_multithreaded_capture
	multi_threaded_capture.cpp
	)
	set(multithreaded_capture_libs
	${PROJECT_NAME}
	${PROJECT_NAME}_image_logging
	${PROJECT_NAME}_image_logging_common
	${PROJECT_NAME}_udp_logging
	${PROJECT_NAME}_udp_logging_common
	${PROJECT_NAME}_proto
	${screen_capture_lite_LIBRARIES}
	${screen_capture_lite_PLATFORM_LIBS}
	${Boost_TARGETS}
	${TBB_IMPORTED_TARGETS}
	${YAML_CPP_LIBRARIES}
	yaml-cpp
	)
	if(NOT HAS_STDCXXFS)
		target_compile_definitions(${PROJECT_NAME}_multithreaded_capture PRIVATE BOOST_FILESYSTEM=1)
	endif(NOT HAS_STDCXXFS)

	if(MSVC)
		if(YAML_CPP_DLL)
			target_compile_definitions(${PROJECT_NAME}_multithreaded_capture PRIVATE "YAML_CPP_DLL")
		endif()
		if(WIN10API)
			list(APPEND multithreaded_capture_libs RuntimeObject)
		endif()
	endif()
	target_link_libraries(${PROJECT_NAME}_multithreaded_capture ${multithreaded_capture_libs})
	list(APPEND install_targets ${PROJECT_NAME}_multithreaded_capture)
endif()
if(WITH_VJOY)
	install(DIRECTORY ${CMAKE_SOURCE_DIR}/tracks/ DESTINATION tracks
        FILES_MATCHING PATTERN "*.track")
endif()
install(TARGETS ${install_targets}
    RUNTIME DESTINATION bin
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
)
unset(install_targets)

