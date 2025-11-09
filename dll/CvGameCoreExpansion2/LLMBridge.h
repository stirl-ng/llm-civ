#pragma once

#include <string>

class NamedPipeClient;

namespace llmbridge {

bool initialize();
void shutdown();
bool send_json(const char* json_utf8);
bool is_connected();
bool receive_next(std::string& json_utf8);
void requeue(const std::string& json_utf8);

// Exported C API
extern "C" __declspec(dllexport) bool LLMBridge_Initialize();
extern "C" __declspec(dllexport) void LLMBridge_Shutdown();
extern "C" __declspec(dllexport) bool LLMBridge_Send(const char* json_utf8);
extern "C" __declspec(dllexport) bool LLMBridge_IsConnected();

}
