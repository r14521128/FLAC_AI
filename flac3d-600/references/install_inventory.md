# FLAC3D 6.00 — Official datafiles inventory

Catalog of `C:\Program Files\Itasca\Flac3d600\datafiles\`. These are the **official Itasca worked examples** shipped with FLAC3D 6.00. They are the v6 idiomatic ground truth — when generating a `.f3dat`, copy patterns from here rather than improvising.

**Total:** 1213 files — 850 `.f3dat`, 167 `.f3prj`, 67 `.dat` (legacy), 43 `.tab`, 24 `.txt`, 18+18 FISH (`.fis`/`.f3fis`), 8 `.stl`, 5 `.f3grid`, 5 `.dxf`.

## Tree at a glance

```
datafiles/
├── ConstitutiveModels/      20 problems, 74 .f3dat   ← element-tests for each cmodel
├── Creep/                   14 problems, 60 .f3dat
├── Dynamic/                 19 problems, 101 .f3dat
├── ExampleApplications/     19 problems, 132 .f3dat  ← realistic engineering cases
├── FISH/                    Library + Tutorial       ← FISH learning material
├── Fluid/                   17 problems, 78 .f3dat   ← groundwater / coupled flow
├── Interface/                5 problems, 17 .f3dat
├── Structure/                6 element types, 75 .f3dat ← Beam/Cable/Geogrid/Liner/Pile/Shell
├── TheoryAndBackground/      2 problems, 24 .f3dat
├── Thermal/                 12 problems, 64 .f3dat
├── UsersGuide/              Fish/Geometry/Intro/ProblemSolving/Tutorial, 147 .f3dat ← READ FIRST
└── VerificationProblems/    13 problems, 72 .f3dat   ← analytical-solution benchmarks
```

Every problem subfolder follows the same convention: `<Problem>.f3prj` + `<Problem>.f3dat` + `master.f3dat` that calls everything in order. `check.f3dat` (when present) is a regression test.

---

## ConstitutiveModels/ — element-test verifications

| Folder | What it shows |
|---|---|
| `OedometerMohrCoulomb` / `OedometerDruckerPrager` / `OedometerCYSoil` / `OedometerPlasticHardening` | 1D consolidation test for each cmodel |
| `DrainedTriaxialCHSoil` / `DrainedTriaxialConstantDilationCYSoil` / `DrainedTriaxialDilationHardeningCYSoil` / `DrainedTriaxialPlasticHardening` | Drained triaxial test for soil cmodels |
| `UndrainedTriaxialCYSoil` / `UndrainedTriaxialPlasticHardening` | Undrained triaxial |
| `IsotropicCompressionCYSoil` / `IsotropicCompressionDoubleYield` / `IsotropicCompressionPlasticHardening` | Isotropic compression |
| `IsotropicConsolidationModifiedCamClay` | Modified Cam-Clay isotropic consolidation |
| `TriaxialCompressionHoekBrown` / `TriaxialCompressionHoekBrownPAC` | Hoek-Brown triaxial (classical + plastic-area-correction) |
| `SingleZoneMohrCoulombTensionCrack` | Tension-cutoff behaviour |
| `SingleZoneSwell` | Swelling cmodel |
| `ComparisonPlasticHardening` / `ComparisonSmallStrainPlasticHardening` | Hardening soil model comparison |

→ When the user picks a constitutive model, the matching folder here is the canonical minimal `.f3dat` template.

## Creep/ — time-dependent material behaviour

`ComparisonWIPPDrucker`, `CompressionClassical`, `CompressionViscoplastic`, `CompressionWIPPDrucker`, `CylindricalCavityPower`, `CylindricalCavityPowerMohr`, `CylindricalCavityWIPP`, `HydrostaticCompressionWIPPSalt`, `OedometerKelvin`, `OedometerMaxwell`, `ParallelPlateViscometerClassical`, `ParallelPlateViscometerWIPP`, `SphericalCavityPower`, `UnconfinedAndBiaxialCompressionWIPPSalt`. Plus the standalone `SetKStrains.f3fis` FISH utility.

## Dynamic/ — time-history / seismic

Damping setup: `Damping-Compare`, `Damping-SpatialVariation`, `MechanicalDamping`, `ArtificialViscosity`.
Wave propagation: `ShearWaveOnVerticalBar`, `ShearWaveFreeFieldBoundModel`, `ShearWaveOnStiffWallInSoftSoil`, `SlipInducedHarmonicShearWave`, `SphericalPulse`, `ShearWithStrainRateReversal`.
Seismic input: `EarthquakeExcitation`, `ShakingTableTest`, `HydroDynamicPressure`, `DamFoundation`, `DamFoundationWet`.
Site response: `F3ShakeLinearElasticCase`, `F3ShakeNonLinearElasticCase`, `SeveralCyclicStrainLevels` (with `…-shake-damping.txt`, `…-shake-modulus-reduction-factor.txt`).
Misc: `NaturalPeriodsElasticColumn`.

## ExampleApplications/ — realistic engineering problems (the gold mine)

Tunnels & excavation:
- `ExcavationAndSupportOfShallowTunnel` — shotcrete + cable-bolt staged tunnel
- `IntersectingTunnels`
- `ReinforcedTunnelExcavation`
- `AnchoredExcavation`, `BracedExcavation`, `HorizontalCut`, `CaissonWithTiebacks`
- `ExcavationInSaturatedSoil` — coupled hydromech excavation

Slopes / footings / loads:
- `SlopeCurvature`
- `EmbankmentLoad`, `WheelLoadOverBuriedPipe`, `PunchIndentation`
- `PressurizedCylindricalCavern`, `BoreholeClosureInSaltFormation`, `CavityExpansion`

Supports & piling:
- `ConcretePile`, `PullTestsRockReinforcement`, `Pillar`, `SleevedTriaxialTest`

## FISH/

| Subfolder | Content |
|---|---|
| `Library/` | Reusable FISH utilities: `der.fis` (derivative), `erfc.fis`, `expint.fis`, `fft.fis`, `filter.fis`, `int.fis` (integration), `spec.fis` (spectra), `topo.fis` (topography), `zonk3d.fis`, `baseline.fis`. Each ships with a `.dat` driver. |
| `Tutorial/` | `fishex1_01.dat` … `fishex2_19.dat` — 33 progressive lessons. `failurestates.fis`, `fishcall.fis`. |

## Fluid/ — groundwater & coupled flow

Consolidation: `1DConsolidation`, `ConsolidationSettlement`, `UndrainedOedometer`, `SoilLayerHeave`, `Swelling`.
Steady state: `FreeSurfaceSteadyStateFluidFlow`, `SemiConfinedAquifer`, `WellConfinedAquifer`, `UnsteadyGroundwaterFlowConfinedLayer`, `GroundwaterMound`.
Pore pressure: `PorePressureGenerationConfined`, `PorePressureGenerationInfinite`, `ZoneBasedPorePressure`, `WeightBuoyancySeepage`.
Other: `1DFillingPorousRegion`, `Footing`, `Pressuremeter`.

→ `Fluid/1DConsolidation/` ships four variants: `-Coupled`, `-Coupled10M`, `-FastFlow`, `-Uncoupled` — canonical for showing the four coupled-flow regimes.

## Interface/ — contact / interface elements

`BinFlowSlip`, `DippingJoint`, `DirectShearTest`, `Subgrids`, `UniaxialCompTest`.

## Structure/ — structural elements (one folder per element type)

| Element | Subfolders |
|---|---|
| `Beam` | `AxialBuckling`, `BracedSupport`, `Cantilever`, `ConcentratedLoads`, `PlasticHinge` |
| `Cable` | `ReinforcedBeam`, `SoilNailing` |
| `Geogrid` | `PullOutTest`, `ReinforcedEmbankment`, `SoilInterfaceTest` |
| `Liner` | `AdvancingLinedTunnel`, `EmbeddedRetainingWall`, `LargeStrainSliding`, `LinerZoneInterfaceTest`, `ReinforcedBeam` |
| `Pile` | `AxiallyLoaded`, `LaterallyLoaded` |
| `Shell` | `AdvancingTunnel`, `Cantilever`, `ConcentratedLoads`, `PlasticHinge`, `PlateAppliedPressure` |

## TheoryAndBackground/

`ElasticBlock`, `FactorOfSafety` — companion data files to theory.pdf chapters.

## Thermal/

`ConcreteInclusion`, `ConcreteWall`, `ConvectionAndConductionThermalTransport`, `HeatGeneratingSlab`, `HollowCylinderConduction`, `HortonRogersLapwoodConvection`, `InfinityLineSource`, `NaturalAdvection`, `PlaneSheetConduction`, `RectangularFin`, `SphericalCavityWithAppliedHeatFlux`, `ThermalPorePressureCoupledResponse`.

## UsersGuide/ — READ FIRST when learning v6

| Subfolder | Content |
|---|---|
| `Tutorial/QuickStart/` | `first.f3dat`, `geometry.f3dat`, `master.f3dat`, `first.f3prj` — minimal end-to-end v6 model |
| `Tutorial/Illustrative/` | `FullTutorial.f3prj`, `tutorial.f3dat`, plus 14 `.f3dat` lessons (grouping, equilibrium, reflecting, regular-radial, simple-brick, sloping-surface, stepping-to-equilibrium, …) |
| `Fish/` | `ug-defining.f3dat`, `ug-variable.f3dat`, `ug-variable-types.f3dat`, `ug-for-loop.f3dat`, `ug-controlled-loop.f3dat`, `ug-if.f3dat`, `ug-array.f3dat`, `ug-map.f3dat`, `ug-history.f3dat`, `ug-derive.f3dat`, `ug-set.f3dat`, `ug-set2.f3dat`, `ug-splitting-lines.f3dat`, `ug-output-1.txt`, `ug-apply-moduli.f3dat`, `ug-automatic-cable.f3dat`, `ug-excavation-sequence.f3dat`, `ug-understanding-test.f3dat`, `ug-using-variables.f3dat` |
| `Geometry/` | 8 numbered `example_*.f3dat` + `geomgroup`, `geomcount`, `geomdist`, `geomtopo[1-6]`, `gendensify`, `geomodd`, `intcylinder.stl`, `s1.dxf`/`s2.dxf`, `Y0.dxf`/`Y1.dxf`/`Y2.dxf`, `surface1.stl`, `fish_cylinder.fis` |
| `Introduction/` | `FiniteVolumeGrid/`, `WhyFISH/` |
| `ProblemSolving/` | 13 conceptual chapters: `BoundaryConditions`, `ConstitutiveModels`, `Equilibrium`, `FactorOfSafety`, `GeometricData`, `GridGeneration`, `IdentifyingRegions`, `InitialConditions`, `Interfaces`, `MaterialModels`, `Miscellaneous`, `Properties`, `SequentialModeling` |

→ For "show me v6 idiomatic syntax", `UsersGuide/Tutorial/QuickStart/first.f3dat` is the single best entry point.

## VerificationProblems/ — closed-form benchmarks

`CircularFooting`, `CylinderInHoekBrownPAC`, `CylinderInMohrCoulomb`, `CylindricalConcreteVault`, `FreeVibration`, `LinedCircularTunnel`, `PlasticHingesBeam`, `PrandtlsWedge`, `SimplySupportedIsotropicPlate`, `SimplySupportedOrthotropicPlate`, `SquareFooting`, `TriaxialCompressionTest`, `UniaxialStrengthJointed`.

Each problem has an analytical solution that the `.f3dat` reproduces — use these to ground accuracy claims.

---

## How to find an example fast

Three approaches in priority order:

1. **By topic** — pick the matching top-level folder, then scan subfolders.
2. **By command** — `Grep` for the command across `datafiles/`:
   ```
   Grep pattern:"zone relax excavate" path:"C:/Program Files/Itasca/Flac3d600/datafiles"
   ```
3. **By problem keyword** — `Glob` on folder names:
   ```
   Glob pattern:"datafiles/**/*Tunnel*/*.f3dat" 
   ```

When citing, use the form: `datafiles/<Topic>/<Problem>/<file>.f3dat`.
