# Lange Mesh for C++

This reference implementation provides [Mesh wire messages](../../reference_documentation/messages/README.md), peer discovery, and local capability dispatch. It requires a C++17 compiler and CMake 3.18 or later.

```sh
cmake -S . -B build
cmake --build build
ctest --test-dir build --output-on-failure
```

Use `add_subdirectory(path/to/mesh/cpp)` and link your application to `lange_mesh::lange_mesh`. CMake uses an installed nlohmann/json 3.12-compatible package when available and otherwise downloads the pinned 3.12.0 release. [nlohmann/json CMake documentation](https://json.nlohmann.me/integration/cmake/)

```cpp
#include <lange_mesh/router.hpp>

#include <iostream>
#include <stdexcept>

int main() {
    using namespace lange_mesh;

    Router router({"local", "Local", 1});
    const Parameter value{"value", std::string("string"), "The value to echo."};
    router.tools().add_to_mesh(
        {"", "echo", "Echo", "Returns the supplied value.", {value}, {value}},
        [](const std::vector<BaseValue>& input) -> ToolResult {
            if (input.size() != 1) {
                throw std::invalid_argument("expected one input");
            }
            return input.front();
        });

    const auto outcome = router.handle_message(parse_message(R"({
        "msg":"do",
        "meta":{"version":1,"node_from":"peer","node_to":"local","hops":["peer"]},
        "payload":{"id":"echo","input":["hello"]}
    })"));

    if (const auto* reply = std::get_if<Message>(&outcome)) {
        std::cout << encode_message(*reply) << '\n';
    }
}
```

Pass each inbound message through `parse_message`. Dispatch returns either a reply `Message` for `encode_message` or a typed `Acknowledgement` for the caller. Serialize concurrent access to each router or tool group in the calling application.

Handlers run synchronously and can return `std::nullopt` for empty outputs. Each other successful result occupies one output slot, including array and object values. Protocol integer fields are signed 64-bit values. Base values support signed and unsigned 64-bit integers and finite double-precision numbers.
