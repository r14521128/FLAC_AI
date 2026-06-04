# D:\FLAC_AI\2D Local Codex Instructions

## Material Parameter Formatting
- When writing `materials_mc`, keep the tuple order as:
  `(density[kg/m3], young[GPa], poisson[-], cohesion[kPa], friction[deg],)`.
- FLAC uses Pa internally, so the code values must still be written in Pa.
- Write `young[GPa]` values using `Ae9` notation whenever possible, so the GPa value is visible at a glance.
  - Example: `1.0e9` means `1.0 GPa = 1.0e9 Pa`.
- Write `cohesion[kPa]` values using `Be3` notation whenever possible, so the kPa value is visible at a glance.
  - Example: `100e3` means `100 kPa = 100,000 Pa`.
  - Do not write `100e6` for `100 kPa`; `100e6 Pa` means `100 MPa`.
