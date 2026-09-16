# Finite Time Blowup for Navier–Stokes

**Authors:** OpenAI  
**PDF:** [papers/pdfs/navier-stokes.pdf](../../papers/pdfs/navier-stokes.pdf)  

## Abstract

An AI-assisted hypothesis-verification review of Finite Time Blowup for Navier–Stokes by OpenAI, testing 3 curated claims via the Moonstar proof-algebra pipeline (hand-transcribed algebraic sub-claims verified symbolically via sympy, cross-examined by an LLM proof critic and devil's advocate). Verdicts: 3 plausible.

## Paper Summary

This paper constructs a smooth solution to the 3D incompressible Navier–Stokes equations with a prescribed force that blows up in finite time, starting from rest and maintaining uniformly bounded kinetic energy. The blowup is driven by an axisymmetric, self-similar vortex core whose radial width scales like τ^{1/2} and axial width like τ^{1/2-h}, with a small positive exponent h, making the core increasingly slender as the singular time approaches. Within this core, the azimuthal and axial velocities grow like τ^{-1/2-h}, while the angular Reynolds number diverges and the radial Reynolds number remains order one, ensuring a precise balance between radial diffusion and transport.

The construction proceeds by building an approximate solution through a matched asymptotic expansion, then correcting its residual via highly structured, spatially oscillatory pulses. The stress from these pulses is cancelled against the leading error using a covariance identity, and the correction is iterated in stages to flatten the residual to all orders in the similarity variable q. A key technical innovation is the use of a "stress cone" condition to ensure that the pulse amplitudes can be chosen with the right sign, along with a careful treatment of the exterior flow as a purely azimuthal heat field that carries no residual.

The proof culminates by localizing the fields, showing that any global smooth competitor would coincide with the constructed solution and thus also blow up, establishing that the force is admissible for the equations and that no smooth global solution exists. The result extends to any positive viscosity by a spatial rescaling, yielding a finite-time singularity for the full 3D Navier–Stokes system with a bounded-energy initial condition and an explicitly constructed body force.

## Methodology

Each hypothesis is tested through Moonstar's proof_hypothesis pipeline: an LLM Extractor pulls hand-transcribed algebraic sub-claims (equations transcribed from the paper by the human author) out of the natural-language hypothesis into structured JSON; each claim is verified symbolically via sympy (AlgebraicClaimsCheckTransform); an LLM proof critic assesses whether the verified algebra would actually support the hypothesis's broader claim; a devil's advocate LLM then challenges the emerging consensus; finally a synthesizer LLM produces the conversational verdict published here. PLAUSIBLE here means only that the transcribed algebra is internally consistent — it never means the underlying theorem is proven. Hypotheses, including their embedded equations, are hand-transcribed by the human author from the source paper before submission to the pipeline, and all pipeline output is reviewed by the author before publication.

Models used: extraction with deepseek/deepseek-v4-flash, critique and synthesis with deepseek/deepseek-v4-pro.

## Tested Hypotheses

| # | Hypothesis | Verdict | Details |
|---|---|---|---|
| 1 | The paper's parameter table (page 14, preceding equation (4.1)) fixes a small exponent h and defines the tangential-velocity growth exponent A = 1/2 + h and the axial-length exponent D = 1/2 − h, both used throughout the self-similar profile construction. These two definitions must sum to exactly 1: A + D = 1. | PLAUSIBLE | [full writeup](#hypothesis-1) |
| 2 | Equation (5.1) writes the pressure coefficient profile as p_n = q^(-2A+λn) * Π_n, using the radial-mode exponent λ_n = 2*n*h from the parameter table together with A = 1/2 + h from the same table. Substituting these two definitions, the combined exponent -2*A + λ_n must simplify to exactly -1 + 2*h*(n-1). | PLAUSIBLE | [full writeup](#hypothesis-2) |
| 3 | Section 10.4's viscosity-rescaling argument (equations (10.22)-(10.23)) extends the viscosity-one construction to every positive viscosity ν by setting v(y,t) = ν^(-1/2) * v_ν(sqrt(ν)*y, t). The paper states this gives the L2-norm scaling relation ||v(t)||_2^2 = ν^(-5/2) * ||v_ν(t)||_2^2. This combined exponent -5/2 must equal the sum of the amplitude-squaring exponent (-1, from squaring the ν^(-1/2) prefactor) and the exponent contributed by the volume element under the substitution y = sqrt(ν)*x in three spatial dimensions (-3/2): -1 + (-3/2) = -5/2. | PLAUSIBLE | [full writeup](#hypothesis-3) |

## Evidence

### Hypothesis 1

**Claim:** The paper's parameter table (page 14, preceding equation (4.1)) fixes a small exponent h and defines the tangential-velocity growth exponent A = 1/2 + h and the axial-length exponent D = 1/2 − h, both used throughout the self-similar profile construction. These two definitions must sum to exactly 1: A + D = 1.

**Verdict:** PLAUSIBLE

The only algebraic claim that was transcribed and checked — that the sum of the two exponents A and D equals 1 — is internally consistent. The identity_checks system verifies symbolic simplification: (1/2 + h) + (1/2 – h) reduces exactly to 1, with a consistent verdict. The proof_critic confirms that this verified identity directly supports the proof_context’s assertion that A + D = 1, with no logical gap in that step.

However, the devil’s advocate raises a crucial point: the overall paper’s theorem very likely requires much more than this one trivial simplification. The pipeline only tested the algebraic step that was explicitly transcribed; any unstated assumptions, additional algebraic manipulations, or dependencies on definitions that were not enumerated remain completely unchecked. The verified step is a small, elementary identity — it does not, on its own, prove the full result. So while the transcribed algebra that we *could* check is indeed consistent, the theorem itself is not established by this pipeline, and the full proof may still contain gaps.

In summary: the single checked algebraic identity is valid, so the verdict on the transcribed algebra is PLAUSIBLE — but that says nothing about whether the larger theorem is actually proved. That would require a complete, step‑by‑step verification of all necessary components, which is beyond what this run examined.

**Deterministic checks:**

- `identity_checks`: consistent

[Raw run data](runs/local-83ac6eb95cc1.json)

### Hypothesis 2

**Claim:** Equation (5.1) writes the pressure coefficient profile as p_n = q^(-2A+λn) * Π_n, using the radial-mode exponent λ_n = 2*n*h from the parameter table together with A = 1/2 + h from the same table. Substituting these two definitions, the combined exponent -2*A + λ_n must simplify to exactly -1 + 2*h*(n-1).

**Verdict:** PLAUSIBLE

The claim under scrutiny is a single algebraic substitution: plugging \(A = \frac{1}{2} + h\) and \(\lambda_n = 2nh\) into the expression \(-2A + \lambda_n\), then simplifying to obtain \(-1 + 2h(n-1)\). The identity check verified this directly — the left-hand side \(-2(\frac{1}{2} + h) + 2nh\) simplifies exactly to \(-1 + 2h(n-1)\), with zero symbolic difference between the claimed and derived forms. The aggregate verdict from identity_checks is "consistent."

The proof critic concurs, noting that this single algebraic step is precisely the transformation described in the proof context, and that no further logical steps are missing within the scope of what was checked. The devil's advocate raises a fair caveat: the verification covers only this one isolated substitution, and "consistent" here does not mean the entire proof has been vetted end-to-end. That caveat is correct — this pipeline can only confirm that the transcribed algebra is internally consistent; it does not and cannot establish the broader theorem or the correctness of any surrounding argument, assumptions, or derivation from elsewhere in the paper.

So the right way to read "PLAUSIBLE" here is narrow: the algebra as transcribed checks out. Whether the choice of \(A\) and \(\lambda_n\), the surrounding derivation, or the ultimate mathematical result is correct is beyond what this verification can demonstrate.

**Deterministic checks:**

- `identity_checks`: consistent

[Raw run data](runs/local-a73a4c5a6bba.json)

### Hypothesis 3

**Claim:** Section 10.4's viscosity-rescaling argument (equations (10.22)-(10.23)) extends the viscosity-one construction to every positive viscosity ν by setting v(y,t) = ν^(-1/2) * v_ν(sqrt(ν)*y, t). The paper states this gives the L2-norm scaling relation ||v(t)||_2^2 = ν^(-5/2) * ||v_ν(t)||_2^2. This combined exponent -5/2 must equal the sum of the amplitude-squaring exponent (-1, from squaring the ν^(-1/2) prefactor) and the exponent contributed by the volume element under the substitution y = sqrt(ν)*x in three spatial dimensions (-3/2): -1 + (-3/2) = -5/2.

**Verdict:** PLAUSIBLE

The identity_checks tool found that, of the two algebraic claims extracted from the paper, one couldn't be parsed at all (the scaling relation for the squared L2‑norm under viscosity rescaling), while the other – an exponent sum identity – was symbolically consistent. The aggregate verdict is therefore “consistent”, meaning the single transcription that could be checked holds up algebraically.  

That is an extremely narrow result. The checked identity simply confirms that −5/2 = −1 + (−3/2); it doesn't touch the heart of the argument, which claims that a self‑similar substitution extends a ν=1 construction to all positive viscosities. The proof_critic explicitly flags that verifying this minor relation is insufficient to demonstrate preservation of the Navier–Stokes equations, handling of boundary or initial conditions, or existence for every viscosity. The devil’s advocate further notes that the central scaling step (the claim that failed to parse) was never verified at all.  

So “PLAUSIBLE” here means only that the one piece of algebra the pipeline could check is internally consistent; it does *not* mean the underlying theorem is proved or even that the paper’s core algebraic steps are sound. The overall claim of a global well‑posedness result remains unsupported by the evidence this pipeline can provide.

**Deterministic checks:**

- `identity_checks`: consistent

[Raw run data](runs/local-5df49f6e15ba.json)

## References

1. OpenAI (n.d.). Finite Time Blowup for Navier–Stokes.
