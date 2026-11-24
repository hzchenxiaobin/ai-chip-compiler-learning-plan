#include "greet.h"

std::string greet(const std::string& name) {
    if (name.empty()) {
        return "Hello, playground!";
    }
    return "Hello, " + name + "!";
}
