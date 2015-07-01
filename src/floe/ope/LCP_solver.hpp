/*!
 * \file ope/LCP_solver.hpp
 * \brief LCP solver
 * \author Quentin Jouet
 */

#ifndef OPE_LCP_SOLVER_HPP
#define OPE_LCP_SOLVER_HPP

#include "floe/lcp/solver/lexicolemke.hpp"
#include "floe/lcp/solver/lemke_eigen.hpp"
#include "floe/lcp/lcp.hpp"
#include "floe/lcp/builder/graph_to_lcp.hpp"
#include <boost/numeric/ublas/vector_proxy.hpp>
#include <boost/numeric/ublas/blas.hpp>
#include <algorithm>


#include <iostream> // debug

namespace floe { namespace ope
{

/*! LCPSolver
 *
 * Operator for LCP solving
 *
 */

using namespace boost::numeric::ublas;

class LCPSolver
{

public:
    using lcp_type = floe::lcp::LCP<double>;

    using value_type = double; // TODO get from trait

    const bool solve( lcp_type& lcp );
    template<typename TContactGraph>
    vector<value_type> solve( TContactGraph& graph, bool& success  );

private:

    lcp_type random_perturbation(lcp_type& lcp, value_type max);

    // TODO put elsewhere
    value_type random_real(value_type max);

    const bool LCPtest(int compt, value_type EC, value_type born_EC, value_type Err, bool VRelNtest );

    template<typename Tmat, typename Tvect>
    value_type calcEc(const Tvect& S, const Tmat& M, const Tvect& w);

    template<typename TGraphLCP>
    vector<value_type>
    calcSol(TGraphLCP& graph_lcp, LCPSolver::lcp_type& lcp);

    template<typename TContactGraph>
    const bool VRelNtest(const vector<value_type>& V, const TContactGraph& graph);

};


template<typename T>
inline const bool is_nan(const T t){
    return (t != t);
}


const bool LCPSolver::solve( lcp_type& lcp ) {
        using namespace floe::lcp::solver;
        return (lemke(lcp) || lexicolemke(lcp));
    }


template<typename TContactGraph>
vector<typename LCPSolver::value_type>
LCPSolver::solve( TContactGraph& graph, bool& success ) {
    using namespace floe::lcp::solver;

    floe::lcp::builder::GraphLCP<value_type, decltype(graph)> graph_lcp( graph );
    auto lcp = graph_lcp.getLCP();
    auto lcp_orig = lcp;

    std::vector<std::vector<int>> MatLCP{
        {1,1},{2,1},{3,1},
        {0,1},{1,1},{2,1},{3,1},
        {0,1},{1,1},{2,1},{3,1},
        {0,2},{1,2},{2,2},{3,2},
        {0,2},{1,2},{2,2},{3,2},
        {0,3},{1,3},{2,3},{3,3},
    };
    int comptchgt{0};
    bool solved{0};
    vector<value_type> Solc(graph_lcp.J.size1());

    decltype(lcp.z) best_z;
    value_type best_Err = std::numeric_limits<value_type>::max();

    while (!solved)
    {
//        comptchgt++;
        if (comptchgt >= MatLCP.size()) // passer le contact
        {
            success = 0;
            return graph_lcp.W; // TODO be sure this is the correct return
        }

        bool success{0};
        switch (MatLCP[comptchgt][0])
        {
            case 0:
                lcp = random_perturbation(lcp, 1e-10); //TODO compare matlab "divmat"
                break;
                // [A,Qc] = divmat(A,Qc,Iheart);
            case 1:
                success = lemke(lcp);
                break;
            case 2:
                success = lexicolemke(lcp);
                break;
            case 3:
                // success = lexicolemke(lcp); // don't have Iterlemke...
                break;
                // zc = IterLemke(Aorigin, Qcorigin, 1e-11, best.zc);
        }
        comptchgt++;

        if (!success)
            continue;

        if (std::any_of(lcp.z.begin(), lcp.z.end(), is_nan<double>))
            continue;

        lcp_orig.z = lcp.z;

         // As-t-on une meilleure solution ?
        auto Err = LCP_error(lcp_orig);
        if (Err < best_Err || best_Err == std::numeric_limits<value_type>::max())
        {
            best_z = lcp.z;
            best_Err = Err;
        }

         // On teste toujours la meilleure solution trouvÃ©e
        lcp_orig.z = best_z;
        Err = best_Err;
        
         // Solution correspondante
        Solc = calcSol(graph_lcp, lcp_orig);

        if (std::any_of(Solc.begin(), Solc.end(), is_nan<double>))
            continue; // std::cout << "******NAN******";

         // Energie cinetique, Erreur LCP & Vit rel Normale :
        auto ECc = calcEc(Solc, graph_lcp.M, graph_lcp.W); // TODO be sure this is the correct 3rd arg
        Err = LCP_error(lcp_orig);
        // vitrelnormtest = VRelNtest(trans(graph_lcp.J) * Solc, dist, Mc); // TODO matlab version
        auto vitrelnormtest = VRelNtest(prod(trans(graph_lcp.J), Solc), graph);
        solved = LCPtest(MatLCP[comptchgt][1],ECc,1,Err,vitrelnormtest);
    }
    success = 1;
    return Solc;

}


const bool LCPSolver::LCPtest(int compt, value_type EC, value_type born_EC, value_type Err, bool VRelNtest ){
    bool resp = 1;
        if (compt == 1)
        {
            if (EC > born_EC*(1+1e-4) || abs(Err) > 1e-11 || VRelNtest == 0)
                resp = 0;
        }
        else if (compt == 2)
        {
            if (EC > born_EC * (1+1e-4) || abs(Err) > 1e-8 || VRelNtest == 0)
                resp = 0;
        }
        else if (compt == 3)
        {
            if (EC > born_EC*(1+1e-2) || VRelNtest == 0)
                resp = 0;
        }
        return resp;
}

template<typename Tmat, typename Tvect>
typename LCPSolver::value_type 
LCPSolver::calcEc(const Tvect& S, const Tmat& M, const Tvect& w){
    return inner_prod(prod(S, M), S) / inner_prod(prod(w, M), w);
}


template<typename TGraphLCP>
vector<LCPSolver::value_type>
LCPSolver::calcSol(TGraphLCP& graph_lcp, LCPSolver::lcp_type& lcp)
{   
    std::size_t m = graph_lcp.J.size2();
    return graph_lcp.W + prod(
        graph_lcp.invM,
        prod(graph_lcp.J, subrange(lcp.z, 0, m)) + prod(graph_lcp.D, subrange(lcp.z, m, 3*m))
    );
}


typename LCPSolver::lcp_type
LCPSolver::random_perturbation(lcp_type& lcp, value_type max){
    for (auto it1 = lcp.A.begin1(); it1 != lcp.A.end1(); ++it1) {
        for (auto it2 = it1.begin(); it2 != it1.end(); ++it2) {
            if (*it2 != 0)
                *it2 += random_real(max);
        }
    }
    return lcp; 
}

template<typename TContactGraph>
const bool LCPSolver::VRelNtest(const vector<value_type>& V, const TContactGraph& graph){
    size_t contact_id = 0;
    for ( auto const& edge : make_iterator_range( boost::edges( graph ) ) )
    {
        // Foreach contact between this 2 floes ...
        for ( auto const& contact : graph[edge] )
        {
            if (V[contact_id] < 0)
            {
                value_type delta = V[contact_id] * DT_DEFAULT; // get dt_defaut otherwise ?
                if (delta > contact.dist / 50)
                    return 0;
            }
            ++contact_id;
        }
    }
    return 1;
}

// TODO put elsewhere ?
typename LCPSolver::value_type 
LCPSolver::random_real(value_type max)
{
    return (value_type)(std::rand() - RAND_MAX / 2) / RAND_MAX * max;
}


}} // namespace floe::ope


#endif // OPE_LCP_SOLVER_HPP