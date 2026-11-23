#include <lange_mesh/types.hpp>

#include <algorithm>
#include <cmath>
#include <type_traits>

namespace lange_mesh {

bool is_valid_value(const BaseValue& value) {
    const auto finite_scalar = [](const auto& scalar) {
        if constexpr (std::is_same_v<std::decay_t<decltype(scalar)>, double>) {
            return std::isfinite(scalar);
        }
        return true;
    };

    return std::visit([&](const auto& item) {
        using Type = std::decay_t<decltype(item)>;
        if constexpr (std::is_same_v<Type, AtomicArray>) {
            return std::all_of(item.begin(), item.end(), [&](const AtomicValue& element) {
                return std::visit(finite_scalar, element);
            });
        } else if constexpr (std::is_same_v<Type, AtomicObject>) {
            return std::all_of(item.begin(), item.end(), [&](const auto& entry) {
                return std::visit(finite_scalar, entry.second);
            });
        } else {
            return finite_scalar(item);
        }
    }, value);
}

} // namespace lange_mesh
