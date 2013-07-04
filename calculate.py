'''
Created on May 31, 2013

@author: ghwatson
'''
from __future__ import division

from scipy import integrate, linalg, spatial
import scipy as sp

import sympy
from sympy.mpmath import cos, sqrt, log, pi
import sympy.mpmath

from sympy.mpmath import mpf, extraprec
from maple import maple_EllipticK, maple_EllipticE, maple_EllipticF #TODO: The maple implementation is ugly, here.  Should pass namespace to the maple object at initiation.
from itertools import chain

class Calculate(object):
    '''
    Class containing calculations used in Casini's paper.
    '''
        
    @staticmethod
    def correlations(polygon, maple_link, precision, precomputed_correlations=None, verbose=False):
        
        # Set the mpmath precision.
        sympy.mpmath.mp.dps = precision
        
        # Compute distance matrix of all possible pairs.
        D = spatial.distance.cdist(polygon,polygon)
        
        # Get the unique distances making up D, as well as id's of D giving these
        # and inverse id's to rebuild D from the unique distances.
        [unique,idx_1d,inv_idx] = sp.unique(D,True,True)
        
        # Convert 1d indices to 2d indices
        idx_2d = sp.unravel_index(idx_1d,D.shape)
        idx_2d = sp.dstack((idx_2d[0],idx_2d[1]))[0]
        
        # Unflatten inv_idx
        inv_idx = sp.reshape(inv_idx,D.shape)
          
        # Calculate all distinct correlator values for V.
        unique_phi_correlations = sympy.mpmath.zeros(unique.shape[0],1) 
        unique_pi_correlations = sympy.mpmath.zeros(unique.shape[0],1)
        
        for idx_1d, [r,r_prime] in enumerate(idx_2d):
            
            # Take difference in coordinates of the pairs to get i,j (i.e. set origin
            # at r for calculating this correlator).
            [i,j] = polygon[r_prime] - polygon[r]
            dist_sq = i*i + j*j
            
            # Check if the correlations have already been found in the precomputed dictionary, otherwise compute them.
    
            if precomputed_correlations is not None and dist_sq in precomputed_correlations.keys():
                unique_phi_correlations[idx_1d], unique_pi_correlations[idx_1d] = precomputed_correlations[dist_sq]
            else:
    
                phi_corr, pi_corr = Calculate.correlators_ij(i,j,maple_link,precision)
                
                # Save.
                unique_phi_correlations[idx_1d] = phi_corr
                unique_pi_correlations[idx_1d] = pi_corr
                
                # Save to precomputed_correlations for optimization of larger lattice calculations.
                if precomputed_correlations is not None:
                    precomputed_correlations[dist_sq] = [phi_corr, pi_corr]
            
            if verbose == True:
                print "Calculated integrals for i,j = {0}".format([i,j])
            
           
        # Populate matrix elements. 
        X = sympy.zeros(inv_idx.shape[0],inv_idx.shape[1])
        P = sympy.zeros(inv_idx.shape[0],inv_idx.shape[1])
        for i in xrange(inv_idx.shape[0]):
            for j in xrange(inv_idx.shape[1]):
                X[i,j] = unique_phi_correlations[inv_idx[i,j]]
                P[i,j] = unique_pi_correlations[inv_idx[i,j]]
        
        if precomputed_correlations is not None:
            return X,P,precomputed_correlations
        else:
            return X,P
        
    @staticmethod
    def correlators_ij(i, j, maple_link, precision):
        '''
        Calculate the integral cos(ix)cos(jy)/sqrt(2(1-cos(x))+2(1-cos(y))) for x,y = -Pi..Pi.
        This is done by computing the inner integral symbolically, and the outer numerically.
        The integral is done on a quarter quadrant since it is symmetric.
        
        :param i: lattice index i
        :param j: lattice index j
        :param maple_link: the MapleLink class to communicate with Maple
        '''
        # Set the mpmath precision.
        sympy.mpmath.mp.dps = precision
        
        # Symbolically solve inner integral, using Maple:
        phi_str = "cos({0}*x)/sqrt(2*(1-cos(x))+2*(1-cos(y)))".format(int(i))
        phi_integ_str = "int({0},x=0..Pi) assuming y >= 0;".format(phi_str)
        pi_str = "cos({0}*x)*sqrt(2*(1-cos(x))+2*(1-cos(y)))".format(int(i))
        pi_integ_str = "int({0},x=0..Pi) assuming y >= 0;".format(pi_str)
        inner_phi_str = maple_link.query(phi_integ_str)
        inner_pi_str = maple_link.query(pi_integ_str)
#             inner_phi_str = maple_link.raw_query(phi_integ_str)
#             inner_pi_str = maple_link.raw_query(pi_integ_str)

        # Create function using maple output. #TODO: switch out the eval for a parser when possible. eval is dangerous.
        def phi_inner_integral(y):
            out = eval(inner_phi_str)
            return out*cos(int(j)*y)
        def pi_inner_integral(y):
            out = eval(inner_pi_str)
            return out*cos(int(j)*y)
         
        # Perform the outer integrals.
        phi_integ = sympy.mpmath.quad(extraprec(1000)(phi_inner_integral),[0,pi])
        pi_integ = sympy.mpmath.quad(extraprec(1000)(pi_inner_integral),[0,pi])

#             # Pass the strings back to maple to integrate again.
#             outer_phi_int = "evalf(int(cos({0}*y)*({1}),y=0..Pi),{2});".format(int(j),inner_phi_str,precision)
#             outer_pi_int = "evalf(int(cos({0}*y)*({1}),y=0..Pi),{2});".format(int(j),inner_pi_str,precision)
#             outer_phi_int = maple_link.raw_query(outer_phi_int)
#             outer_pi_int = maple_link.raw_query(outer_pi_int)
#             phi_integ = mpf(outer_phi_int)
#             pi_integ = mpf(outer_pi_int)
        
        phi_integ *= mpf('1')/(2*pi**2)
        pi_integ *= mpf('1')/(2*pi**2)
        
        return phi_integ,pi_integ

    @staticmethod
    def entropy(X, P, n,precision, verbose=False):
        '''
        Calculates the nth Renyi entropy for the polygonal set, as Casini does
        numerically in his paper.
        
        :param polygon: a Nx2 scipy.array of points composing the polygon region.
        :param n: the Renyi index.
        :param maple_link: link to Maple's command line, using MapleLink class.
        '''
    
        # Get the eigenvalues of sqrt(XP)
        print sympy.mpmath.mp.dps
        with extraprec(500):
            XP = X*P
    #         v = XP.eigenvals()
    #         sqrt_eigs = []
    #         for eig, mult in v.iteritems():
    #             sqrt_eigs.append([sqrt(sympy.re(sympy.N(eig,precision)))] * mult)
    #         sqrt_eigs = list(chain.from_iterable((sqrt_eigs)))
        
        #Scipy eigenvalues.
        #TODO: see if this works, given mpmath structure.
        XPnum = sympy.matrix2numpy(XP)
        speigs = linalg.eigvals(XPnum)
        sqrtspeigs = sp.sqrt(speigs)
        sqrt_eigs = sqrtspeigs
        
        # Check that the eigenvalues are well-defined.
        for eig in sqrt_eigs:
            if eig.real <= 0.5:
                raise ValueError("At least one of the eigenvalues of sqrt(XP) is below 0.5! \n eig = {0}".format(eig))
            if eig.imag != 0:
                raise ValueError("Warning: getting imaginary components in eigenvalues! \n imag = {0}".format(eig.imag))
        
        # Convert to float. Chop off imaginary component.
        sqrt_eigs = sqrt_eigs.real
        
        # Calculate entropy.
        S_n = 0
        my_eps = 1.e-8
        if n == 1:
            for vk in sqrt_eigs:
                S_n += ((vk + 0.5)*log(vk + 0.5) - (vk - 0.5)*log(vk - 0.5 + my_eps))
        else:
            for vk in sqrt_eigs:
                S_n += log((vk + 0.5)**n - (vk - 0.5)**n)
            S_n *= 1./(n-1)
            
        if verbose==True:
            print "Calculated entropy of {0}".format(S_n)
            
        S_n = float(S_n)
        return S_n

    @staticmethod
    def square_lattice(L):
        '''
        Generates an array of points making up a square LxL lattice.
        
        :param L: the dimension of the square lattice.
        '''
        x = sp.linspace(0,L,L+1)
        coord_arrays = sp.meshgrid(x,x)
        polygon = (sp.dstack(coord_arrays))
        polygon = sp.reshape(polygon,((L+1)**2,2))    
        return polygon