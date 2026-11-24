#include "greet.h"
#include <cassert>
#include <iostream>
#include <string>

int main() {
    assert(greet("CANNBot") == "Hello, CANNBot!");
    assert(greet("") == "Hello, playground!");
    assert(greet(std::string(64, 'x')).size() == 64 + 8);
    std::cout << "all 3 greet tests passed\n";
    return 0;
}
