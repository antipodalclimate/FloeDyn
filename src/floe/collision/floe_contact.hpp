/*!
 * \file floe/collision/floe_contact.hpp
 * \brief Contact between two floes.
 * \author Quentin Jouet
 */

#ifndef FLOE_COLLISION_FLOE_CONTACT_HPP
#define FLOE_COLLISION_FLOE_CONTACT_HPP

#include <vector>
#include <memory>


namespace floe { namespace collision
{

/*! Contact point between two floes.
 *
 * \tparam TContactPoint   contact point type.
 */

template <
    typename TContactPoint
>
class FloeContact : public std::vector<TContactPoint>
{

public:
    using base_class = std::vector<TContactPoint>;
    FloeContact() : base_class(), m_solved{std::make_shared<bool> (true)}, m_id_ifloe1{0}, m_id_ifloe2{0} {}
    FloeContact(base_class& contact_list, std::size_t n1, std::size_t n2) : 
        base_class(contact_list), m_solved{std::make_shared<bool> (true)}, m_id_ifloe1{n1}, m_id_ifloe2{n2} {}
    FloeContact(FloeContact<TContactPoint> const& fc) = default;

    inline void mark_solved( bool solved = true ) const { *m_solved = solved; }
    inline bool is_solved() const { return *m_solved; }
    inline std::size_t n1() const { return m_id_ifloe1; }
    inline std::size_t n2() const { return m_id_ifloe2; }

private:
    // bool ptr (owned by other object)
    // mutable bool m_solved;
    mutable std::shared_ptr<bool> m_solved;
    std::size_t m_id_ifloe1; // floe interface (real or ghost)
    std::size_t m_id_ifloe2;

};


}} // namespace floe::collision

#endif // FLOE_COLLISION_FLOE_CONTACT_HPP
