"""Onboarding: versioned consent and the branching questionnaire (U3; ADR-007).

Other modules import only :mod:`app.onboarding.public`. Medical answers never leave this
package: the public read port returns non-medical answers only.
"""
