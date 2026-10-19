FeatureScript 3095;
import(path : "onshape/std/geometry.fs", version : "3095.0");

/**
 * eMachine: one feature for every machine of the emachine project (tickets T43 to T47).
 *
 * Choose the machine as the project names it (docs/naming.md): flux path, torque principle and
 * rotor layout, then type in the inputs of a specification (outer diameter, stack, air gap, bore)
 * and the design variables of a design ("python -m emachine onshape" lists them). The other
 * dimensions follow from these as in the Python model (emRfmDimensions, emTfmDimensions), so stator
 * and rotor always fit together; inputs that leave no room stop with a message naming the fields.
 * The machine axis is the world Z axis.
 *
 *   TFM (transverse flux) PMSM: the "TFM stator" and "TFM rotor" code (copied below as functions
 *       by "python -m emachine featurescript"); stator layouts U, UI, toothed ring, claw pole, C,
 *       E, Z; rotor layouts Halbach, surface, spoke, axial ring.
 *   RFM (radial flux), inner rotor: the 2D cross-section of machines/rfm/section.py extruded over
 *       the stack, from Z = -L/2 to L/2: slotted stator with parallel-sided slots, coil sides in
 *       the slot halves coloured by phase (slot star, double or single layer), shaft, and the rotor
 *       of the layout: surface magnets (PMSM), interior V magnets (PMSM), flux barriers with or
 *       without magnets (SynRM, PM-assisted SynRM), salient teeth (SRM). The rotor is turned so
 *       that the d axis of pole 1 lies on the axis of phase 1, as in the field solution.
 *   Not built yet (the feature stops with the ticket): Vernier (B15), RAFM (B14), AFM (B10, B11),
 *   TFM SRM (B12), RFM with an outer rotor.
 *
 * Interior, flux barrier and salient rotors are drawn here before the analysis has them (B06 to
 * B09): their dimensions follow the variables of machines/rfm/rotors/, the shapes are simple.
 */

export enum EmFluxPath
{
    annotation { "Name" : "TFM: transverse flux" }
    TFM,
    annotation { "Name" : "RFM: radial flux" }
    RFM,
    annotation { "Name" : "AFM: axial flux" }
    AFM,
    annotation { "Name" : "RAFM: radial-axial flux" }
    RAFM
}

export enum EmPrinciple
{
    annotation { "Name" : "PMSM: permanent magnet synchronous" }
    PMSM,
    annotation { "Name" : "SynRM: synchronous reluctance" }
    SYNRM,
    annotation { "Name" : "SRM: switched reluctance" }
    SRM,
    annotation { "Name" : "Vernier (PM vernier, flux modulation)" }
    VERNIER
}

export enum EmRotor
{
    annotation { "Name" : "Halbach array" }
    HALBACH,
    annotation { "Name" : "Surface magnets (SPM)" }
    SURFACE,
    annotation { "Name" : "Inset magnets" }
    INSET,
    annotation { "Name" : "Interior magnets (IPM, V)" }
    INTERIOR,
    annotation { "Name" : "Spoke (flux concentrating)" }
    SPOKE,
    annotation { "Name" : "Axial ring magnet between toothed discs" }
    AXIAL_RING,
    annotation { "Name" : "Flux barriers (SynRM)" }
    FLUX_BARRIER,
    annotation { "Name" : "Flux barriers with magnets (PMaSynRM)" }
    FLUX_BARRIER_PM,
    annotation { "Name" : "Salient iron poles (SRM)" }
    SALIENT
}

export enum EmStator
{
    annotation { "Name" : "U-core" }
    U_CORE,
    annotation { "Name" : "U-core with I-bridge" }
    UI_CORE,
    annotation { "Name" : "C-core" }
    C_CORE,
    annotation { "Name" : "E-core" }
    E_CORE,
    annotation { "Name" : "Z-core" }
    Z_CORE,
    annotation { "Name" : "Claw pole" }
    CLAW_POLE,
    annotation { "Name" : "Toothed ring (Fig. 17)" }
    TOOTHED_RING
}

export enum EmRotorPlacement
{
    annotation { "Name" : "Inner rotor" }
    INNER,
    annotation { "Name" : "Outer rotor" }
    OUTER
}

export enum EmWindingSpan
{
    annotation { "Name" : "Concentrated (tooth coils)" }
    CONCENTRATED,
    annotation { "Name" : "Distributed (overlapping coils)" }
    DISTRIBUTED
}

// ---------------------------------------------------------------- bounds

const EM_1MM_BOUNDS = { (meter) : [0, 0.001, 500], (centimeter) : 0.1, (millimeter) : 1.0, (inch) : 0.04 } as LengthBoundSpec;
const EM_2MM_BOUNDS = { (meter) : [1e-5, 0.002, 500], (centimeter) : 0.2, (millimeter) : 2.0, (inch) : 0.08 } as LengthBoundSpec;
const EM_10MM_BOUNDS = { (meter) : [0, 0.010, 500], (centimeter) : 1.0, (millimeter) : 10.0, (inch) : 0.4 } as LengthBoundSpec;
const EM_100MM_BOUNDS = { (meter) : [1e-4, 0.100, 500], (centimeter) : 10.0, (millimeter) : 100.0, (inch) : 4.0 } as LengthBoundSpec;
const EM_PHASES_BOUNDS = { (unitless) : [1, 3, 6] } as IntegerBoundSpec;
const EM_POLE_PAIRS_BOUNDS = { (unitless) : [1, 5, 500] } as IntegerBoundSpec;
const EM_SLOTS_BOUNDS = { (unitless) : [3, 12, 500] } as IntegerBoundSpec;
const EM_LAYERS_BOUNDS = { (unitless) : [1, 2, 2] } as IntegerBoundSpec;
const EM_PITCH_BOUNDS = { (unitless) : [0, 0, 500] } as IntegerBoundSpec;
const EM_COUNT_BOUNDS = { (unitless) : [1, 3, 12] } as IntegerBoundSpec;
const EM_ROTOR_POLES_BOUNDS = { (unitless) : [2, 8, 500] } as IntegerBoundSpec;
const EM_EL_ARC_BOUNDS = { (degree) : [0, 150, 180], (radian) : 2.618 } as AngleBoundSpec;
const EM_POLE_ARC_BOUNDS = { (degree) : [0, 20, 180], (radian) : 0.349 } as AngleBoundSpec;
const EM_SHIFT_BOUNDS = { (degree) : [-90, 0, 90], (radian) : 0 } as AngleBoundSpec;
const EM_V_ANGLE_BOUNDS = { (degree) : [60, 135, 180], (radian) : 2.356 } as AngleBoundSpec;

// Constants of the TFM geometry (machines/tfm/design.py; docs/parameters.md, "Constants of the geometry")
const EM_BRIDGE_TOP_RATIO = 0.8;
const EM_HALBACH_SEGMENTS = 2;

/**
 * Field values of a new feature: the 12-slot 10-pole surface PM machine of specs/rfm_spm_12s10p*.json.
 * The TFM fields hold a design that fits the same outer diameter and stack.
 */
const EM_DEFAULTS = {
            "fluxPath" : EmFluxPath.RFM, "principle" : EmPrinciple.PMSM, "rotor" : EmRotor.SURFACE,
            "rotorPlacement" : EmRotorPlacement.INNER, "phases" : 3,
            "outerDiameter" : 100 * millimeter, "stackLength" : 40 * millimeter, "airGap" : 0.7 * millimeter,
            "boreDiameter" : 20 * millimeter, "polePairs" : 5, "yokeHeight" : 8 * millimeter,
            "slotHeight" : 12 * millimeter, "magnetThickness" : 3 * millimeter, "magnetArc" : 153 * degree,
            // TFM
            "stator" : EmStator.UI_CORE, "phaseSpacing" : 1 * millimeter, "poleShift" : 0 * degree, "toothArc" : 144 * degree,
            "legWidth" : 2 * millimeter, "rotorIron" : 3 * millimeter,
            "bridgeHeight" : 2 * millimeter, "ringToothHeight" : 8 * millimeter, "archedValleys" : false,
            "staggeredTeeth" : false, "clawRootHeight" : 3 * millimeter, "clawTipHeight" : 2 * millimeter,
            "clawTipGap" : 1.5 * millimeter, "coilClearance" : 0.5 * millimeter, "coilMargin" : 1 * millimeter,
            "magnetHeight" : 8 * millimeter,
            // RFM
            "slots" : 12, "slotWidth" : 7.07 * millimeter,
            "windingSpan" : EmWindingSpan.CONCENTRATED, "layers" : 2, "pitchSlots" : 0,
            "magnetLength" : 5.5 * millimeter, "vAngle" : 135 * degree, "bridge" : 1 * millimeter,
            "barriers" : 3, "barrierWidth" : 1 * millimeter, "rib" : 0.8 * millimeter, "magnetWidth" : 4 * millimeter,
            "rotorPoles" : 8, "rotorPoleArc" : 18 * degree, "rotorPoleHeight" : 4 * millimeter,
            "includeStator" : true, "includeCoil" : true, "includeRotor" : true
        };

annotation { "Feature Type Name" : "eMachine",
        "Feature Type Description" : "A machine of the emachine project: flux path, torque principle and rotor layout, with the inputs and design variables of a specification." }
export const eMachine = defineFeature(function(context is Context, id is Id, definition is map)
    precondition
    {
        annotation { "Name" : "Flux path" }
        definition.fluxPath is EmFluxPath;

        annotation { "Name" : "Torque principle" }
        definition.principle is EmPrinciple;

        annotation { "Name" : "Rotor layout" }
        definition.rotor is EmRotor;

        annotation { "Name" : "Rotor placement" }
        definition.rotorPlacement is EmRotorPlacement;

        annotation { "Name" : "Number of phases" }
        isInteger(definition.phases, EM_PHASES_BOUNDS);

        annotation { "Name" : "Outer diameter" }
        isLength(definition.outerDiameter, EM_100MM_BOUNDS);

        annotation { "Name" : "Stack length (all phases)" }
        isLength(definition.stackLength, EM_100MM_BOUNDS);

        annotation { "Name" : "Air gap" }
        isLength(definition.airGap, EM_1MM_BOUNDS);

        annotation { "Name" : "Bore diameter (shaft, or the free bore inside an inner stator)" }
        isLength(definition.boreDiameter, EM_10MM_BOUNDS);

        if (definition.principle != EmPrinciple.SRM)
        {
            annotation { "Name" : "Pole pairs" }
            isInteger(definition.polePairs, EM_POLE_PAIRS_BOUNDS);
        }

        annotation { "Name" : "Yoke height" }
        isLength(definition.yokeHeight, EM_2MM_BOUNDS);

        annotation { "Name" : "Slot height" }
        isLength(definition.slotHeight, EM_10MM_BOUNDS);

        if (definition.fluxPath == EmFluxPath.TFM)
        {
            annotation { "Name" : "Stator layout" }
            definition.stator is EmStator;

            annotation { "Name" : "Phase spacing" }
            isLength(definition.phaseSpacing, EM_1MM_BOUNDS);

            annotation { "Name" : "Pole shift (electrical)" }
            isAngle(definition.poleShift, EM_SHIFT_BOUNDS);

            annotation { "Name" : "Tooth arc (electrical, 180: whole pole pitch)" }
            isAngle(definition.toothArc, EM_EL_ARC_BOUNDS);

            annotation { "Name" : "Leg width" }
            isLength(definition.legWidth, EM_2MM_BOUNDS);

            if (definition.rotorPlacement == EmRotorPlacement.OUTER)
            {
                annotation { "Name" : "Rotor iron (housing behind the magnets)" }
                isLength(definition.rotorIron, EM_2MM_BOUNDS);
            }

            if (definition.stator == EmStator.UI_CORE)
            {
                annotation { "Name" : "I-bridge height" }
                isLength(definition.bridgeHeight, EM_2MM_BOUNDS);
            }

            if (definition.stator == EmStator.TOOTHED_RING)
            {
                annotation { "Name" : "Ring tooth height" }
                isLength(definition.ringToothHeight, EM_2MM_BOUNDS);

                annotation { "Name" : "Arched valleys between teeth", "Default" : false }
                definition.archedValleys is boolean;

                annotation { "Name" : "Staggered teeth (back wall one pole pitch later)", "Default" : false }
                definition.staggeredTeeth is boolean;
            }

            if (definition.stator == EmStator.CLAW_POLE)
            {
                annotation { "Name" : "Claw root height" }
                isLength(definition.clawRootHeight, EM_2MM_BOUNDS);

                annotation { "Name" : "Claw tip height" }
                isLength(definition.clawTipHeight, EM_2MM_BOUNDS);

                annotation { "Name" : "Claw tip gap" }
                isLength(definition.clawTipGap, EM_1MM_BOUNDS);
            }

            annotation { "Name" : "Coil clearance" }
            isLength(definition.coilClearance, EM_1MM_BOUNDS);

            annotation { "Name" : "Coil margin (to the pole face or the I-bridge)" }
            isLength(definition.coilMargin, EM_1MM_BOUNDS);

            if (definition.rotor == EmRotor.SPOKE)
            {
                annotation { "Name" : "Spoke magnet radial height" }
                isLength(definition.magnetHeight, EM_10MM_BOUNDS);
            }
        }

        if (definition.fluxPath == EmFluxPath.RFM)
        {
            annotation { "Name" : "Slots" }
            isInteger(definition.slots, EM_SLOTS_BOUNDS);

            annotation { "Name" : "Slot width (parallel-sided slot)" }
            isLength(definition.slotWidth, EM_2MM_BOUNDS);

            annotation { "Name" : "Winding span" }
            definition.windingSpan is EmWindingSpan;

            annotation { "Name" : "Winding layers" }
            isInteger(definition.layers, EM_LAYERS_BOUNDS);

            annotation { "Name" : "Coil pitch in slots (0: 1 or full pitch)" }
            isInteger(definition.pitchSlots, EM_PITCH_BOUNDS);
        }

        if (definition.fluxPath == EmFluxPath.TFM ||
            (definition.fluxPath == EmFluxPath.RFM && (definition.rotor == EmRotor.SURFACE || definition.rotor == EmRotor.INTERIOR)))
        {
            annotation { "Name" : "Magnet thickness (spoke: magnet width)" }
            isLength(definition.magnetThickness, EM_2MM_BOUNDS);
        }

        if (definition.rotor == EmRotor.SURFACE || definition.rotor == EmRotor.AXIAL_RING)
        {
            annotation { "Name" : "Magnet arc (electrical, 180: whole pole)" }
            isAngle(definition.magnetArc, EM_EL_ARC_BOUNDS);
        }

        if (definition.fluxPath == EmFluxPath.RFM && definition.rotor == EmRotor.INTERIOR)
        {
            annotation { "Name" : "Magnet length (each bar of the V)" }
            isLength(definition.magnetLength, EM_10MM_BOUNDS);

            annotation { "Name" : "V angle (180: one flat bar)" }
            isAngle(definition.vAngle, EM_V_ANGLE_BOUNDS);

            annotation { "Name" : "Bridge to the rotor surface" }
            isLength(definition.bridge, EM_1MM_BOUNDS);
        }

        if (definition.fluxPath == EmFluxPath.RFM && (definition.rotor == EmRotor.FLUX_BARRIER || definition.rotor == EmRotor.FLUX_BARRIER_PM))
        {
            annotation { "Name" : "Flux barriers per pole" }
            isInteger(definition.barriers, EM_COUNT_BOUNDS);

            annotation { "Name" : "Barrier width" }
            isLength(definition.barrierWidth, EM_1MM_BOUNDS);

            annotation { "Name" : "Rib" }
            isLength(definition.rib, EM_1MM_BOUNDS);

            if (definition.rotor == EmRotor.FLUX_BARRIER_PM)
            {
                annotation { "Name" : "Magnet width (across the q axis)" }
                isLength(definition.magnetWidth, EM_2MM_BOUNDS);
            }
        }

        if (definition.fluxPath == EmFluxPath.RFM && definition.principle == EmPrinciple.SRM)
        {
            annotation { "Name" : "Rotor poles" }
            isInteger(definition.rotorPoles, EM_ROTOR_POLES_BOUNDS);

            annotation { "Name" : "Rotor pole arc (mechanical)" }
            isAngle(definition.rotorPoleArc, EM_POLE_ARC_BOUNDS);

            annotation { "Name" : "Rotor pole height" }
            isLength(definition.rotorPoleHeight, EM_2MM_BOUNDS);
        }

        annotation { "Name" : "Include stator", "Default" : true }
        definition.includeStator is boolean;

        annotation { "Name" : "Include coils", "Default" : true }
        definition.includeCoil is boolean;

        annotation { "Name" : "Include rotor", "Default" : true }
        definition.includeRotor is boolean;
    }
    {
        emCheckMatrix(definition);
        if (definition.fluxPath == EmFluxPath.TFM)
            emTfm(context, id, definition);
        else
            emRfm(context, id, definition);
    }, EM_DEFAULTS);

// ---------------------------------------------------------------- the machine matrix

/** Stops with the ticket when the chosen flux path, principle and rotor layout are not built (docs/machines.md). */
function emCheckMatrix(definition is map)
{
    const fp = definition.fluxPath;
    const pr = definition.principle;
    if (pr == EmPrinciple.VERNIER)
        throw regenError("The PM vernier machine is not built yet (ticket B15).", ["principle"]);
    if (fp == EmFluxPath.RAFM)
        throw regenError("The radial-axial flux machine is not built yet (ticket B14).", ["fluxPath"]);
    if (fp == EmFluxPath.AFM)
        throw regenError("Axial flux machines are not built yet (tickets B10 and B11; B16 for the SynRM).", ["fluxPath"]);
    if (fp == EmFluxPath.TFM)
    {
        if (pr == EmPrinciple.SYNRM)
            throw regenError("A transverse flux SynRM is not a machine: each TFM phase has a pulsating field of its own. The reluctance TFM is the SRM (ticket B12).", ["principle"]);
        if (pr == EmPrinciple.SRM)
            throw regenError("The transverse flux SRM is not built yet (ticket B12).", ["principle"]);
        if (definition.rotor != EmRotor.HALBACH && definition.rotor != EmRotor.SURFACE &&
            definition.rotor != EmRotor.SPOKE && definition.rotor != EmRotor.AXIAL_RING)
            throw regenError("TFM PMSM rotor layouts: Halbach array, surface magnets, spoke, axial ring magnet.", ["rotor"]);
        return;
    }
    // RFM
    if (definition.rotorPlacement == EmRotorPlacement.OUTER)
        throw regenError("The radial flux machines are built with an inner rotor only.", ["rotorPlacement"]);
    if (pr == EmPrinciple.PMSM && definition.rotor != EmRotor.SURFACE && definition.rotor != EmRotor.INTERIOR)
        throw regenError("RFM PMSM rotor layouts: surface magnets, interior magnets (inset magnets: not offered yet).", ["rotor"]);
    if (pr == EmPrinciple.SYNRM && definition.rotor != EmRotor.FLUX_BARRIER && definition.rotor != EmRotor.FLUX_BARRIER_PM)
        throw regenError("RFM SynRM rotor layouts: flux barriers, flux barriers with magnets.", ["rotor"]);
    if (pr == EmPrinciple.SRM && definition.rotor != EmRotor.SALIENT)
        throw regenError("RFM SRM rotor layout: salient iron poles.", ["rotor"]);
}

// ---------------------------------------------------------------- TFM

/**
 * Dimensions of a TFM from the inputs, as design.derived and design.to_parameters of
 * machines/tfm/design.py: the phases share the stack, each phase is a stator ring of two legs
 * around the coil slot; an inner rotor sits inside the stator, an outer rotor around it.
 */
function emTfmDimensions(d is map) returns map
{
    const outer = d.rotorPlacement == EmRotorPlacement.OUTER;
    const ui = d.stator == EmStator.UI_CORE;
    const cp = d.stator == EmStator.CLAW_POLE;
    const tr = d.stator == EmStator.TOOTHED_RING;
    const spoke = d.rotor == EmRotor.SPOKE;
    const width = (d.stackLength - (d.phases - 1) * d.phaseSpacing) / d.phases;
    const slotWidth = width - 2 * d.legWidth;
    const clawRoot = cp ? d.clawRootHeight : 0 * meter;
    const clawTip = cp ? d.clawTipHeight : 0 * meter;
    const windowTop = clawRoot + d.slotHeight;
    const height = windowTop + d.yokeHeight;
    const magnet = spoke ? d.magnetHeight : d.magnetThickness;
    const rOut = d.outerDiameter / 2;
    const bore = d.boreDiameter / 2;
    var statorRadius;
    var rotorGapRadius;
    var statorFar;
    if (outer)
    {
        rotorGapRadius = rOut - d.rotorIron - magnet;
        statorRadius = rotorGapRadius - d.airGap;
        statorFar = statorRadius - height;
    }
    else
    {
        statorRadius = rOut - height;
        rotorGapRadius = statorRadius - d.airGap;
        statorFar = rOut;
    }
    const bridge = ui ? d.bridgeHeight : 0 * meter;
    const coilHeight = cp ? d.slotHeight - 2 * d.coilClearance : d.slotHeight - d.coilClearance - d.coilMargin - bridge;

    if (width <= 0 * meter)
        throw regenError("The phase spacing uses up the whole stack length.", ["phaseSpacing", "stackLength"]);
    if (slotWidth <= 2 * d.coilClearance)
        throw regenError("No coil slot is left: the two legs fill the width of one phase.", ["legWidth", "stackLength"]);
    if (coilHeight <= 0 * meter)
        throw regenError("No room for the coil: the slot height is used up by the clearance, the margin and the I-bridge.", ["slotHeight"]);
    if (outer && statorFar <= bore)
        throw regenError("The stator reaches into the bore: reduce the slot or yoke height, or the bore diameter.", ["boreDiameter", "slotHeight", "yokeHeight"]);
    if (!outer && rotorGapRadius - magnet <= bore)
        throw regenError("No room for the rotor iron between the magnets and the shaft.", ["boreDiameter", "magnetThickness", "slotHeight", "yokeHeight"]);
    if (tr && d.ringToothHeight >= d.slotHeight)
        throw regenError("The ring tooth height must be smaller than the slot height.", ["ringToothHeight", "slotHeight"]);

    const oneRow = cp || (tr && d.staggeredTeeth);
    var rows = oneRow ? 1 : 2;
    var rowGap = oneRow ? 0 * meter : slotWidth;
    if (d.rotor == EmRotor.AXIAL_RING)
    {
        rows = 1;
        rowGap = slotWidth;
    }
    return { "outer" : outer, "phaseWidth" : width, "slotWidth" : slotWidth, "clawRoot" : clawRoot, "clawTip" : clawTip,
            "statorRadius" : statorRadius, "rotorGapRadius" : rotorGapRadius, "coilHeight" : coilHeight,
            "rows" : rows, "rowGap" : rowGap, "magnet" : magnet };
}

/** The TFM PMSM: the "TFM stator" and "TFM rotor" functions with the dimensions of emTfmDimensions. */
function emTfm(context is Context, id is Id, definition is map)
{
    const g = emTfmDimensions(definition);
    const cores = { EmStator.U_CORE : TfmCoreType.U_CORE, EmStator.UI_CORE : TfmCoreType.UI_CORE,
            EmStator.C_CORE : TfmCoreType.C_CORE, EmStator.E_CORE : TfmCoreType.E_CORE,
            EmStator.Z_CORE : TfmCoreType.Z_CORE, EmStator.CLAW_POLE : TfmCoreType.CP_CORE,
            EmStator.TOOTHED_RING : TfmCoreType.TR_CORE };
    const rotors = { EmRotor.HALBACH : TfmRotorType.HALBACH, EmRotor.SURFACE : TfmRotorType.SURFACE,
            EmRotor.SPOKE : TfmRotorType.FLUX_CONCENTRATING, EmRotor.AXIAL_RING : TfmRotorType.AXIAL };
    if (definition.includeStator)      // the TFM coil is part of the stator feature
    {
        tfmStator(context, id + "stator", {
                    "coreType" : cores[definition.stator],
                    "arrangement" : TfmArrangement.ROTARY,
                    "airGapRadius" : g.statorRadius,
                    "rotaryPolePairs" : definition.polePairs,
                    "innerStator" : g.outer,
                    "trimPoleFaces" : true,
                    "phases" : definition.phases,
                    "phaseSpacing" : definition.phaseSpacing,
                    "poleShift" : definition.poleShift / definition.polePairs,
                    "toothSpan" : definition.toothArc / (180 * degree),
                    "legWidth" : definition.legWidth,
                    "slotWidth" : g.slotWidth,
                    "slotHeight" : definition.slotHeight,
                    "yokeHeight" : definition.yokeHeight,
                    "bridgeHeight" : definition.stator == EmStator.UI_CORE ? definition.bridgeHeight : 1 * millimeter,
                    "bridgeTopRatio" : EM_BRIDGE_TOP_RATIO,
                    "ringToothHeight" : definition.ringToothHeight,
                    "archedValleys" : definition.archedValleys,
                    "staggeredTeeth" : definition.staggeredTeeth,
                    "clawRootHeight" : g.clawRoot,
                    "clawTipHeight" : g.clawTip,
                    "clawTipGap" : definition.clawTipGap,
                    "includeCoil" : definition.includeCoil,
                    "coilHeight" : g.coilHeight,
                    "coilClearance" : definition.coilClearance
                });
    }
    if (definition.includeRotor)
    {
        var rotor = {
            "configuration" : g.outer ? TfmRotorConfiguration.OUTRUNNER : TfmRotorConfiguration.INRUNNER,
            "rotorType" : rotors[definition.rotor],
            "stackLength" : g.phaseWidth,
            "phases" : definition.phases,
            "phaseSpacing" : definition.phaseSpacing,
            "poles" : 2 * definition.polePairs,
            "magnetThickness" : definition.magnetThickness,
            "magnetArcRatio" : definition.magnetArc / (180 * degree),
            "segmentsPerPole" : EM_HALBACH_SEGMENTS,
            "fcMagnetHeight" : definition.magnetHeight,
            "fcMagnetWidth" : definition.magnetThickness,
            "magnetRows" : g.rows,
            "rowGap" : g.rowGap,
            "alternateRows" : g.rows > 1,
            "includeEndCap" : false,
            "showArrows" : true
        };
        if (g.outer)
        {
            rotor.outrunnerInnerDiameter = 2 * g.rotorGapRadius;
            rotor.outrunnerOuterDiameter = definition.outerDiameter;
        }
        else
        {
            rotor.outerDiameter = 2 * g.rotorGapRadius;
            rotor.shaftDiameter = definition.boreDiameter;
        }
        tfmInrunnerRotor(context, id + "rotor", rotor);
    }
}

// ---------------------------------------------------------------- RFM

const EM_PHASE_COLORS = [color(0.85, 0.45, 0.18), color(0.20, 0.45, 0.80), color(0.25, 0.60, 0.30),
        color(0.60, 0.30, 0.70), color(0.85, 0.75, 0.20), color(0.40, 0.40, 0.40)];
const EM_PHASE_NAMES = ["A", "B", "C", "D", "E", "F"];
const EM_STEEL = color(0.62, 0.62, 0.64);
const EM_ROTOR_STEEL = color(0.42, 0.43, 0.46);
const EM_NORTH = color(0.80, 0.15, 0.15);
const EM_SOUTH = color(0.15, 0.60, 0.25);

/**
 * Dimensions of a slotted radial flux machine from the inputs, as SlottedMachine.derive of
 * machines/base.py: from the outer diameter inwards the yoke and the slot (parallel-sided, of the
 * given width) give the bore; the tooth is narrowest at the bore; the rotor sits one air gap inside.
 */
function emRfmDimensions(d is map) returns map
{
    const rOut = d.outerDiameter / 2;
    const rBore = rOut - d.yokeHeight - d.slotHeight;
    const rotorRadius = rBore - d.airGap;
    const shaft = d.boreDiameter / 2;
    if (rotorRadius <= shaft)
        throw regenError("Yoke and slot height leave no room for the rotor around the shaft: reduce them or the bore diameter.", ["yokeHeight", "slotHeight", "boreDiameter"]);
    const tooth = 2 * PI * rBore / d.slots - d.slotWidth;
    if (tooth <= 0 * meter)
        throw regenError("No tooth is left between the slots at the bore: reduce the slot width or the slots.", ["slotWidth", "slots"]);
    if (d.rotor == EmRotor.SURFACE && rotorRadius - d.magnetThickness <= shaft)
        throw regenError("No room for the rotor yoke between the magnets and the shaft.", ["magnetThickness", "boreDiameter"]);
    if (d.principle == EmPrinciple.SRM && rotorRadius - d.rotorPoleHeight <= shaft)
        throw regenError("No room for the rotor core under the poles.", ["rotorPoleHeight", "boreDiameter"]);
    return { "boreRadius" : rBore, "slotDepth" : d.slotHeight, "slotWidth" : d.slotWidth, "statorOuterRadius" : rOut,
            "rotorRadius" : rotorRadius, "shaftRadius" : shaft, "toothWidth" : tooth };
}

/** Radial flux machine, inner rotor: the cross-section extruded from Z = -L/2 to L/2. */
function emRfm(context is Context, id is Id, input is map)
{
    const g = emRfmDimensions(input);
    const definition = mergeMaps(input, g);
    const srm = definition.principle == EmPrinciple.SRM;
    const p = srm ? floor(definition.rotorPoles / 2) : definition.polePairs;
    const coils = emWinding(definition.slots, p, definition.phases, definition.windingSpan == EmWindingSpan.CONCENTRATED,
            definition.layers, definition.pitchSlots);
    const z0 = -definition.stackLength / 2;
    const L = definition.stackLength;
    const rs = g.boreRadius;
    const rd = rs + g.slotDepth;
    const w = g.slotWidth;
    const q = definition.slots;

    if (definition.includeStator)
    {
        const statorId = id + "stator";
        emCylinder(context, statorId + "outer", g.statorOuterRadius, z0, L);
        emCylinder(context, statorId + "bore", rs, z0, L);
        opBoolean(context, statorId + "ring", {
                    "tools" : qCreatedBy(statorId + "bore", EntityType.BODY),
                    "targets" : qCreatedBy(statorId + "outer", EntityType.BODY),
                    "operationType" : BooleanOperationType.SUBTRACTION
                });
        for (var k = 0; k < q; k += 1)
            emProfile(context, statorId + "slots" + ("s" ~ k), z0, L, emSlot(rs, rd, w, k * 360 / q, -1));
        opBoolean(context, statorId + "cutSlots", {
                    "tools" : emSolids(statorId + "slots"),
                    "targets" : qCreatedBy(statorId + "outer", EntityType.BODY),
                    "operationType" : BooleanOperationType.SUBTRACTION
                });
        emStyle(context, qCreatedBy(statorId + "outer", EntityType.BODY), "Stator core", EM_STEEL);
    }

    if (definition.includeCoil)
    {
        const coilId = id + "coil";
        for (var i = 0; i < size(coils.sides); i += 1)
        {
            const side = coils.sides[i];
            const sideId = coilId + ("s" ~ i);
            emProfile(context, sideId, z0, L, emSlot(rs, rd, w, side.slot * 360 / q, side.half));
            emStyle(context, qCreatedBy(sideId, EntityType.BODY),
                    "Coil " ~ EM_PHASE_NAMES[side.phase % 6] ~ (side.sign > 0 ? "+" : "-"), EM_PHASE_COLORS[side.phase % 6]);
        }
    }

    if (definition.includeRotor)
    {
        const offset = emFluxAxisDeg(coils, q, p);
        const rr = g.rotorRadius;
        const rotorId = id + "rotor";
        if (g.shaftRadius > 1e-6 * meter)
        {
            emCylinder(context, rotorId + "shaft", g.shaftRadius, z0, L);
            emStyle(context, qCreatedBy(rotorId + "shaft", EntityType.BODY), "Shaft", color(0.30, 0.30, 0.32));
        }
        const bodyId = rotorId + "body";
        if (definition.rotor == EmRotor.SURFACE)
            emSurfaceRotor(context, bodyId, definition, p, rr, offset, z0, L);
        else if (definition.rotor == EmRotor.INTERIOR)
            emInteriorRotor(context, bodyId, definition, p, rr, offset, z0, L);
        else if (definition.rotor == EmRotor.FLUX_BARRIER || definition.rotor == EmRotor.FLUX_BARRIER_PM)
            emBarrierRotor(context, bodyId, definition, p, rr, offset, z0, L);
        else
            emSalientRotor(context, bodyId, definition, rr, z0, L);
    }
}

/** Surface magnets on a rotor yoke; magnet j is centred at offset + j * 180 / p and is a north pole for even j. */
function emSurfaceRotor(context is Context, id is Id, definition is map, p is number, rr is ValueWithUnits,
    offset is number, z0 is ValueWithUnits, L is ValueWithUnits)
{
    const hm = definition.magnetThickness;
    emAnnulus(context, id + "core", definition.shaftRadius, rr - hm, z0, L);
    emStyle(context, qCreatedBy(id + "core", EntityType.BODY), "Rotor core", EM_ROTOR_STEEL);
    const span = definition.magnetArc / degree / p;         // electrical to mechanical degrees
    for (var j = 0; j < 2 * p; j += 1)
    {
        const centre = offset + j * 180 / p;
        const magnetId = id + "magnets" + ("m" ~ j);
        emProfile(context, magnetId, z0, L, emRingSector(rr - hm, rr, centre - span / 2, centre + span / 2));
        emMagnetStyle(context, magnetId, j % 2 == 0);
    }
}

/** Interior magnets: per pole a V of two rectangular magnets opening towards the air gap, with a bridge of iron above. */
function emInteriorRotor(context is Context, id is Id, definition is map, p is number, rr is ValueWithUnits,
    offset is number, z0 is ValueWithUnits, L is ValueWithUnits)
{
    emAnnulus(context, id + "core", definition.shaftRadius, rr, z0, L);
    const t = definition.magnetThickness;
    const legLength = definition.magnetLength;
    const a = definition.vAngle / 2;                       // angle between a leg and the pole axis
    const dirX = cos(a);
    const dirY = sin(a);
    // Legs start where their inner corners meet on the pole axis, so the two magnets do not overlap.
    const start = (t / 2) * (dirX / max(dirY, 1e-6)) + 0.1 * millimeter;
    const x0 = rr - definition.bridge - (start + legLength) * dirX - (t / 2) * dirY;
    for (var j = 0; j < 2 * p; j += 1)
    {
        const axis = offset + j * 180 / p;
        for (var s = -1; s <= 1; s += 2)
        {
            const u = vector(dirX, s * dirY);              // along the leg
            const n = vector(-s * dirY, dirX);             // across it
            const base = vector(x0, 0 * meter);
            const p0 = base + start * u;
            const p1 = base + (start + legLength) * u;
            const corners = [p0 - (t / 2) * n, p1 - (t / 2) * n, p1 + (t / 2) * n, p0 + (t / 2) * n];
            var points = [];
            for (var c in corners)
                points = append(points, emRotate(c, axis));
            emPolygon(context, id + "magnets" + ("m" ~ j ~ "_" ~ (s + 1)), z0, L, points);
        }
    }
    opBoolean(context, id + "pockets", {
                "tools" : emSolids(id + "magnets"),
                "targets" : qCreatedBy(id + "core", EntityType.BODY),
                "operationType" : BooleanOperationType.SUBTRACTION,
                "keepTools" : true
            });
    emStyle(context, qCreatedBy(id + "core", EntityType.BODY), "Rotor core", EM_ROTOR_STEEL);
    for (var j = 0; j < 2 * p; j += 1)
        for (var s = 0; s <= 2; s += 2)
            emMagnetStyle(context, id + "magnets" + ("m" ~ j ~ "_" ~ s), j % 2 == 0);
}

/**
 * Flux barriers (SynRM): around every q axis, `barriers` bands on circles centred on the q axis
 * outside the rotor, at the distance where the largest circle meets the rotor surface at right
 * angles on the neighbouring d axes. Ribs of iron stay at the rotor surface and around the shaft.
 * With magnets (PMaSynRM), the middle of every barrier is a magnet.
 */
function emBarrierRotor(context is Context, id is Id, definition is map, p is number, rr is ValueWithUnits,
    offset is number, z0 is ValueWithUnits, L is ValueWithUnits)
{
    emAnnulus(context, id + "core", definition.shaftRadius, rr, z0, L);
    const beta = 90 / p * degree;                          // half a pole pitch
    const rc = rr / cos(beta);                             // centre of the barrier circles, on the q axis
    const rhoMax = rr * tan(beta);
    const rhoMin = rc - rr;                                // reaches the rotor surface on the q axis
    const nb = definition.barriers;
    const pitch = (rhoMax - rhoMin) / nb;
    const t = definition.barrierWidth;
    if (t >= pitch)
        throw regenError("The barriers do not fit: the barrier width must stay below the pitch of the barriers (" ~ roundToPrecision(pitch / millimeter, 2) ~ " mm).", ["barrierWidth", "barriers"]);
    const pm = definition.rotor == EmRotor.FLUX_BARRIER_PM;
    // All barriers first, then the magnets: operations under one parent id must follow each other.
    for (var j = 0; j < 2 * p; j += 1)
    {
        const centre = emRotate(vector(rc, 0 * meter), offset + (j + 0.5) * 180 / p);
        for (var b = 0; b < nb; b += 1)
            emBarrier(context, id + "barriers" + ("b" ~ j ~ "_" ~ b), centre, rhoMin + (b + 0.5) * pitch, t,
                    rr - definition.rib, definition.shaftRadius + definition.rib, z0, L);
    }
    for (var j = 0; j < 2 * p; j += 1)
    {
        const axis = offset + (j + 0.5) * 180 / p;
        const centre = emRotate(vector(rc, 0 * meter), axis);
        for (var b = 0; b < nb; b += 1)
        {
            const rho = rhoMin + (b + 0.5) * pitch;
            if (pm)
            {
                // the middle of the barrier: the band within half the magnet width of the q axis
                const magnetId = id + "magnets" + ("m" ~ j ~ "_" ~ b);
                emBarrier(context, magnetId, centre, rho, t, rr - definition.rib, definition.shaftRadius + definition.rib, z0, L);
                const half = definition.magnetWidth / 2;
                const zero = 0 * meter;
                emPolygon(context, magnetId + "box", z0, L, [emRotate(vector(zero, -half), axis),
                            emRotate(vector(rc, -half), axis), emRotate(vector(rc, half), axis),
                            emRotate(vector(zero, half), axis)]);
                opBoolean(context, magnetId + "cut", {
                            "tools" : emSolids(magnetId),       // the barrier copy and the box
                            "operationType" : BooleanOperationType.INTERSECTION
                        });
                emStyle(context, emSolids(magnetId),
                        "Magnet (assisting, q axis " ~ (j + 1) ~ ")", j % 2 == 0 ? EM_NORTH : EM_SOUTH);
            }
        }
    }
    opBoolean(context, id + "cutBarriers", {
                "tools" : emSolids(id + "barriers"),
                "targets" : qCreatedBy(id + "core", EntityType.BODY),
                "operationType" : BooleanOperationType.SUBTRACTION
            });
    emStyle(context, qCreatedBy(id + "core", EntityType.BODY), "Rotor core (flux barriers)", EM_ROTOR_STEEL);
}

/** One barrier band: the ring rho - t/2 .. rho + t/2 around `centre`, inside the circle rOut and outside rIn (both around Z). */
function emBarrier(context is Context, id is Id, centre is Vector, rho is ValueWithUnits, t is ValueWithUnits,
    rOut is ValueWithUnits, rIn is ValueWithUnits, z0 is ValueWithUnits, L is ValueWithUnits)
{
    emCylinderAt(context, id + "band", centre, rho + t / 2, z0, L);
    emCylinderAt(context, id + "hole", centre, rho - t / 2, z0, L);
    opBoolean(context, id + "ring", {
                "tools" : qCreatedBy(id + "hole", EntityType.BODY),
                "targets" : qCreatedBy(id + "band", EntityType.BODY),
                "operationType" : BooleanOperationType.SUBTRACTION
            });
    emCylinder(context, id + "rotor", rOut, z0, L);
    opBoolean(context, id + "inside", {
                "tools" : qUnion([qCreatedBy(id + "band", EntityType.BODY), qCreatedBy(id + "rotor", EntityType.BODY)]),
                "operationType" : BooleanOperationType.INTERSECTION
            });
    emCylinder(context, id + "shaftRib", rIn, z0, L);
    opBoolean(context, id + "clear", {                      // the intersection result belongs to "inside"
                "tools" : qCreatedBy(id + "shaftRib", EntityType.BODY),
                "targets" : qCreatedBy(id + "inside", EntityType.BODY),
                "operationType" : BooleanOperationType.SUBTRACTION
            });
}

/** Salient rotor (SRM): a core with rotorPoles teeth, tooth k centred at k * 360 / rotorPoles. */
function emSalientRotor(context is Context, id is Id, definition is map, rr is ValueWithUnits, z0 is ValueWithUnits, L is ValueWithUnits)
{
    const nr = definition.rotorPoles;
    const h = definition.rotorPoleHeight;
    emAnnulus(context, id + "core", definition.shaftRadius, rr - h, z0, L);
    const span = definition.rotorPoleArc / degree;
    for (var k = 0; k < nr; k += 1)
        emProfile(context, id + "teeth" + ("t" ~ k), z0, L, emRingSector(rr - h - 0.01 * millimeter, rr, k * 360 / nr - span / 2, k * 360 / nr + span / 2));
    opBoolean(context, id + "union", {
                "tools" : qUnion([qCreatedBy(id + "core", EntityType.BODY), emSolids(id + "teeth")]),
                "operationType" : BooleanOperationType.UNION
            });
    emStyle(context, emSolids(id), "Rotor (salient poles)", EM_ROTOR_STEEL);
}

// ---------------------------------------------------------------- winding (slot star, machines/winding_layout.py)

/**
 * Coil sides of the winding: map with `sides` (slot, half 0 clockwise / 1 counter-clockwise, phase,
 * sign), `coils` (slotIn, phase, sign) and `pitch`. Double layer: a coil starts in every slot.
 * Single layer: every second coil, so that each slot holds one side (drawn in both halves).
 */
function emWinding(slots is number, p is number, m is number, concentrated is boolean, layers is number, pitchGiven is number) returns map
{
    var pitch = pitchGiven;
    if (pitch < 1)
        pitch = concentrated ? 1 : max(1, round(slots / (2 * p)));
    const belt = 360 / (2 * m);
    var all = [];
    for (var k = 0; k < slots; k += 1)
    {
        const angle = emMod(p * k * 360 / slots, 360);
        const index = floor(emMod(angle + belt / 2, 360) / belt);
        const sign = index % 2 == 0 ? 1 : -1;
        const lag = emMod(index * belt - (sign > 0 ? 0 : 180), 360);
        const phase = round(lag / (360 / m)) % m;
        all = append(all, { "slotIn" : k, "phase" : phase, "sign" : sign });
    }
    var coils = all;
    if (layers == 1)
    {
        coils = undefined;
        for (var choice = 0; choice < 4 && coils == undefined; choice += 1)
        {
            var chosen = [];
            for (var c in all)
            {
                if ((choice == 0 && c.slotIn % 2 == 0) || (choice == 1 && c.slotIn % 2 == 1) ||
                    (choice == 2 && c.sign > 0) || (choice == 3 && c.sign < 0))
                    chosen = append(chosen, c);
            }
            if (emCoversEverySlot(chosen, slots, pitch) && emBalanced(chosen, m))
                coils = chosen;
        }
        if (coils == undefined)
            throw regenError("These slots and poles give no balanced single-layer winding with a pitch of " ~ pitch ~ " slots.");
    }
    if (!emBalanced(coils, m))
        throw regenError("These slots and poles give no balanced winding.");
    var sides = [];
    for (var c in coils)
    {
        const outSlot = (c.slotIn + pitch) % slots;
        if (layers == 2)
        {
            sides = append(sides, { "slot" : c.slotIn, "half" : 1, "phase" : c.phase, "sign" : c.sign });
            sides = append(sides, { "slot" : outSlot, "half" : 0, "phase" : c.phase, "sign" : -c.sign });
        }
        else
        {
            for (var half = 0; half < 2; half += 1)
            {
                sides = append(sides, { "slot" : c.slotIn, "half" : half, "phase" : c.phase, "sign" : c.sign });
                sides = append(sides, { "slot" : outSlot, "half" : half, "phase" : c.phase, "sign" : -c.sign });
            }
        }
    }
    return { "sides" : sides, "coils" : coils, "pitch" : pitch };
}

function emCoversEverySlot(coils is array, slots is number, pitch is number) returns boolean
{
    var used = makeArray(slots, 0);
    for (var c in coils)
    {
        used[c.slotIn] += 1;
        used[(c.slotIn + pitch) % slots] += 1;
    }
    for (var count in used)
        if (count != 1)
            return false;
    return true;
}

function emBalanced(coils is array, m is number) returns boolean
{
    var counts = makeArray(m, 0);
    for (var c in coils)
        counts[c.phase] += 1;
    for (var count in counts)
        if (count != counts[0] || count == 0)
            return false;
    return true;
}

/** Mechanical angle (degrees) of the d axis of phase 1: where a north pole gives the phase its largest flux. */
function emFluxAxisDeg(winding is map, slots is number, p is number) returns number
{
    var re = 0;
    var im = 0;
    for (var c in winding.coils)
    {
        if (c.phase != 0)
            continue;
        const centre = (c.slotIn + winding.pitch / 2) * 360 / slots;
        re += c.sign * cos(p * centre * degree);
        im += c.sign * sin(p * centre * degree);
    }
    return (atan2(im, re) / degree + 180) / p;
}

function emMod(x is number, n is number) returns number
{
    return ((x % n) + n) % n;
}

// ---------------------------------------------------------------- shapes

/** Point at radius r and angle (degrees) in the XY plane. */
function emPoint(r is ValueWithUnits, angleDeg is number) returns Vector
{
    return vector(r * cos(angleDeg * degree), r * sin(angleDeg * degree));
}

/** A 2D point turned about the origin by angleDeg. */
function emRotate(point is Vector, angleDeg is number) returns Vector
{
    const c = cos(angleDeg * degree);
    const s = sin(angleDeg * degree);
    return vector(point[0] * c - point[1] * s, point[0] * s + point[1] * c);
}

/**
 * Outline of a parallel-sided slot of width w centred at angleDeg, between the circles rIn and
 * rOut (as machines/rfm/section.py): half -1 the whole slot, 0 its clockwise half, 1 the other.
 */
function emSlot(rIn is ValueWithUnits, rOut is ValueWithUnits, w is ValueWithUnits, angleDeg is number, half is number) returns array
{
    const y0 = half == 1 ? 0 * meter : -w / 2;
    const y1 = half == 0 ? 0 * meter : w / 2;
    const ym = (y0 + y1) / 2;
    const xIn = function(y) { return sqrt(rIn * rIn - y * y); };
    const xOut = function(y) { return sqrt(rOut * rOut - y * y); };
    const pts = [vector(xIn(y0), y0), vector(xOut(y0), y0), vector(xOut(ym), ym), vector(xOut(y1), y1),
            vector(xIn(y1), y1), vector(xIn(ym), ym)];
    var r = [];
    for (var pt in pts)
        r = append(r, emRotate(pt, angleDeg));
    return [[r[0], r[1]], [r[1], r[2], r[3]], [r[3], r[4]], [r[4], r[5], r[0]]];
}

/** Outline of the ring sector rIn .. rOut between the angles a0 and a1 (degrees). */
function emRingSector(rIn is ValueWithUnits, rOut is ValueWithUnits, a0 is number, a1 is number) returns array
{
    const am = (a0 + a1) / 2;
    return [[emPoint(rIn, a0), emPoint(rOut, a0)], [emPoint(rOut, a0), emPoint(rOut, am), emPoint(rOut, a1)],
            [emPoint(rOut, a1), emPoint(rIn, a1)], [emPoint(rIn, a1), emPoint(rIn, am), emPoint(rIn, a0)]];
}

/** Extrudes a closed outline (segments [start, end] or arcs [start, mid, end]) from z0 by L along +Z. */
function emProfile(context is Context, id is Id, z0 is ValueWithUnits, L is ValueWithUnits, segments is array)
{
    const zero = 0 * meter;
    const sketch = newSketchOnPlane(context, id + "sketch", {
                "sketchPlane" : plane(vector(zero, zero, z0), vector(0, 0, 1), vector(1, 0, 0))
            });
    for (var i = 0; i < size(segments); i += 1)
    {
        const s = segments[i];
        if (size(s) == 2)
            skLineSegment(sketch, "e" ~ i, { "start" : s[0], "end" : s[1] });
        else
            skArc(sketch, "e" ~ i, { "start" : s[0], "mid" : s[1], "end" : s[2] });
    }
    skSolve(sketch);
    opExtrude(context, id + "extrude", {
                "entities" : qSketchRegion(id + "sketch"),
                "direction" : vector(0, 0, 1),
                "endBound" : BoundingType.BLIND,
                "endDepth" : L
            });
    opDeleteBodies(context, id + "deleteSketch", { "entities" : qCreatedBy(id + "sketch", EntityType.BODY) });
}

/** Extrudes a closed polygon (2D points) from z0 by L. */
function emPolygon(context is Context, id is Id, z0 is ValueWithUnits, L is ValueWithUnits, points is array)
{
    var segments = [];
    for (var i = 0; i < size(points); i += 1)
        segments = append(segments, [points[i], points[(i + 1) % size(points)]]);
    emProfile(context, id, z0, L, segments);
}

/** Cylinder of radius r about the Z axis from z0 to z0 + L. */
function emCylinder(context is Context, id is Id, r is ValueWithUnits, z0 is ValueWithUnits, L is ValueWithUnits)
{
    emCylinderAt(context, id, vector(0 * meter, 0 * meter), r, z0, L);
}

/** Cylinder of radius r about the axis through the 2D point centre, from z0 to z0 + L. */
function emCylinderAt(context is Context, id is Id, centre is Vector, r is ValueWithUnits, z0 is ValueWithUnits, L is ValueWithUnits)
{
    fCylinder(context, id, {
                "bottomCenter" : vector(centre[0], centre[1], z0),
                "topCenter" : vector(centre[0], centre[1], z0 + L),
                "radius" : r
            });
}

/** Ring rIn .. rOut about the Z axis (a cylinder when rIn is zero), from z0 to z0 + L. */
function emAnnulus(context is Context, id is Id, rIn is ValueWithUnits, rOut is ValueWithUnits, z0 is ValueWithUnits, L is ValueWithUnits)
{
    emCylinder(context, id + "outer", rOut, z0, L);
    if (rIn > 1e-6 * meter)
    {
        emCylinder(context, id + "hole", rIn, z0, L);
        opBoolean(context, id + "cut", {
                    "tools" : qCreatedBy(id + "hole", EntityType.BODY),
                    "targets" : qCreatedBy(id + "outer", EntityType.BODY),
                    "operationType" : BooleanOperationType.SUBTRACTION
                });
    }
}

/** Solid bodies created by the operations below `id`. */
function emSolids(id is Id) returns Query
{
    return qBodyType(qCreatedBy(id, EntityType.BODY), BodyType.SOLID);
}

function emStyle(context is Context, bodies is Query, name is string, appearance)
{
    setProperty(context, { "entities" : bodies, "propertyType" : PropertyType.NAME, "value" : name });
    setProperty(context, { "entities" : bodies, "propertyType" : PropertyType.APPEARANCE, "value" : appearance });
}

function emMagnetStyle(context is Context, id is Id, north is boolean)
{
    emStyle(context, qCreatedBy(id, EntityType.BODY), north ? "Magnet N (radial out)" : "Magnet S (radial in)",
            north ? EM_NORTH : EM_SOUTH);
}

// ================================================================ generated below
// The TFM stator and rotor code, copied from machines/tfm/cad/featurescript by
// "emachine featurescript". Edit tfm_stator.fs and tfm_rotor.fs, not this copy.
/**
 * TFM stator
 *
 * Parametric stator core structures of transverse flux machines (TFM), after
 * B. Kaiser and N. Parspour, "Transverse Flux Machine - A Review",
 * IEEE Access, vol. 10, 2022, Fig. 4 (a)-(f), and the one-piece toothed ring of Fig. 17.
 *
 * Local frame used for every core element:
 *   X = direction of motion (pole pitch direction)
 *   Y = transverse direction (coil cross-section lies in the Y-Z plane)
 *   Z = normal to the air gap, pointing from the air gap into the stator
 *   Z = 0 is the pole-face plane.
 *
 * "Linear segment" lays the elements out along X, exactly like Fig. 4.
 * "Rotary ring" wraps X around the world Z axis at the air-gap radius and
 * replaces the straight coil by a ring coil.
 */

export enum TfmCoreType
{
    annotation { "Name" : "U-core" }
    U_CORE,
    annotation { "Name" : "U-core with I-bridge" }
    UI_CORE,
    annotation { "Name" : "Toothed ring (Fig. 17)" }
    TR_CORE,
    annotation { "Name" : "C-core" }
    C_CORE,
    annotation { "Name" : "Claw-pole (CP) core" }
    CP_CORE,
    annotation { "Name" : "E-core" }
    E_CORE,
    annotation { "Name" : "Z-core" }
    Z_CORE
}

export enum TfmArrangement
{
    annotation { "Name" : "Linear segment" }
    LINEAR,
    annotation { "Name" : "Rotary ring" }
    ROTARY
}

// ---------------------------------------------------------------- bounds

const TFM_1MM_BOUNDS = {
            (meter) : [1e-5, 0.001, 500],
            (centimeter) : 0.1,
            (millimeter) : 1.0,
            (inch) : 0.04,
            (foot) : 0.003,
            (yard) : 0.001
        } as LengthBoundSpec;

const TFM_2MM_BOUNDS = {
            (meter) : [1e-5, 0.002, 500],
            (centimeter) : 0.2,
            (millimeter) : 2.0,
            (inch) : 0.08,
            (foot) : 0.006,
            (yard) : 0.002
        } as LengthBoundSpec;

const TFM_6MM_BOUNDS = {
            (meter) : [1e-5, 0.006, 500],
            (centimeter) : 0.6,
            (millimeter) : 6.0,
            (inch) : 0.25,
            (foot) : 0.02,
            (yard) : 0.006
        } as LengthBoundSpec;

const TFM_8MM_BOUNDS = {
            (meter) : [1e-5, 0.008, 500],
            (centimeter) : 0.8,
            (millimeter) : 8.0,
            (inch) : 0.3,
            (foot) : 0.025,
            (yard) : 0.008
        } as LengthBoundSpec;

const TFM_10MM_BOUNDS = {
            (meter) : [1e-5, 0.010, 500],
            (centimeter) : 1.0,
            (millimeter) : 10.0,
            (inch) : 0.4,
            (foot) : 0.03,
            (yard) : 0.01
        } as LengthBoundSpec;

const TFM_12MM_BOUNDS = {
            (meter) : [1e-5, 0.012, 500],
            (centimeter) : 1.2,
            (millimeter) : 12.0,
            (inch) : 0.5,
            (foot) : 0.04,
            (yard) : 0.012
        } as LengthBoundSpec;

const TFM_20MM_BOUNDS = {
            (meter) : [1e-5, 0.020, 500],
            (centimeter) : 2.0,
            (millimeter) : 20.0,
            (inch) : 0.8,
            (foot) : 0.065,
            (yard) : 0.02
        } as LengthBoundSpec;

const TFM_25MM_BOUNDS = {
            (meter) : [1e-5, 0.025, 500],
            (centimeter) : 2.5,
            (millimeter) : 25.0,
            (inch) : 1.0,
            (foot) : 0.08,
            (yard) : 0.025
        } as LengthBoundSpec;

const TFM_60MM_BOUNDS = {
            (meter) : [1e-4, 0.060, 500],
            (centimeter) : 6.0,
            (millimeter) : 60.0,
            (inch) : 2.4,
            (foot) : 0.2,
            (yard) : 0.065
        } as LengthBoundSpec;

const TFM_LINEAR_PAIRS_BOUNDS = { (unitless) : [1, 2, 500] } as IntegerBoundSpec;
const TFM_ROTARY_PAIRS_BOUNDS = { (unitless) : [4, 16, 500] } as IntegerBoundSpec;
const TFM_TOOTH_SPAN_BOUNDS = { (unitless) : [0.1, 0.8, 1.0] } as RealBoundSpec;
const TFM_SKEW_BOUNDS = { (unitless) : [0.05, 0.6, 1.0] } as RealBoundSpec;
const TFM_BRIDGE_TOP_BOUNDS = { (unitless) : [0.05, 0.8, 2.0] } as RealBoundSpec;
const TFM_PHASES_BOUNDS = { (unitless) : [1, 1, 6] } as IntegerBoundSpec;
const TFM_POLE_SHIFT_BOUNDS = { (degree) : [-45, 0, 45], (radian) : 0 } as AngleBoundSpec;

// --------------------------------------------------------------- feature

/** The "TFM stator" feature, as a function: fields not given take the defaults of the feature. */
function tfmStator(context is Context, id is Id, given is map)
{
    const definition = mergeMaps(TFM_STATOR_DEFAULTS, given);
    const coreType = definition.coreType;
    const rotary = definition.arrangement == TfmArrangement.ROTARY;

    // ------------------------------------------------------- layout
    var layout = {
        "rotary" : rotary,
        "sign" : 1,
        "radius" : 0 * meter,
        "poleAngle" : 0 * radian,
        "tau" : 0 * meter,
        "shift" : 0, // extra offset of every second core element, in pole pitches (review paper, Fig. 17)
        "phases" : 1, // phases side by side along the axis (Fig. 5a)
        "phasePitch" : 0 * meter, // axial distance between neighbouring phases
        "phaseStep" : 0 // angular offset between neighbouring phases, in pole pitches
    };
    var polePairs = 1;
    if (rotary)
    {
        polePairs = definition.rotaryPolePairs;
        layout.radius = definition.airGapRadius;
        layout.sign = definition.innerStator ? -1 : 1;
        layout.poleAngle = (PI / polePairs) * radian;
        layout.tau = definition.airGapRadius * PI / polePairs;
        layout.shift = definition.poleShift / layout.poleAngle;
        layout.phases = definition.phases;
        // 360 electrical degrees are two pole pitches; two phases are set 90 degrees apart.
        layout.phaseStep = definition.phases == 2 ? 0.5 : 2 / definition.phases;
        if (coreType == TfmCoreType.CP_CORE && abs(layout.shift) > 1e-9)
            throw regenError("The pole shift is not available for the claw-pole core, whose frames are linked.", ["poleShift"]);
    }
    else
    {
        polePairs = definition.linearPolePairs;
        layout.tau = definition.polePitch;
    }

    const tau = layout.tau;
    const t = definition.toothSpan * tau; // core thickness along the motion direction
    const half = t / 2;
    const wLeg = definition.legWidth;
    const wSlot = definition.slotWidth;
    const hSlot = definition.slotHeight;
    const hYoke = definition.yokeHeight;
    const zero = 0 * meter;

    // ------------------------------------- per-type overall envelope
    var hw = wSlot / 2 + wLeg; // outer half width in Y
    var zWindowTop = hSlot; // top of the coil window
    var coilCenters = [zero]; // Y positions of the coil centres
    var xMax = half; // largest |X| of one rigid core element
    var trimmable = true;

    if (coreType == TfmCoreType.C_CORE)
    {
        xMax = (tau + t) / 2;
        trimmable = false; // air gaps are the inner leg faces
    }
    else if (coreType == TfmCoreType.CP_CORE)
    {
        zWindowTop = definition.clawRootHeight + hSlot;
    }
    else if (coreType == TfmCoreType.E_CORE)
    {
        hw = definition.midLegWidth / 2 + wSlot + wLeg;
        const yCoil = definition.midLegWidth / 2 + wSlot / 2;
        coilCenters = [-yCoil, yCoil];
        xMax = (tau + t) / 2;
    }
    else if (coreType == TfmCoreType.Z_CORE)
    {
        zWindowTop = definition.zToothHeight + hSlot;
        trimmable = false; // air gap is enclosed between tooth and return limb
    }
    else if (coreType == TfmCoreType.TR_CORE && definition.archedValleys)
    {
        trimmable = false; // the walls start at the air-gap cylinder
    }
    const zTop = zWindowTop + hYoke;
    if (rotary && definition.phases > 1)
        layout.phasePitch = 2 * hw + definition.phaseSpacing;
    const phaseSpan = (layout.phases - 1) * layout.phasePitch; // axial room taken by the further phases

    // --------------------------------------------------- validation
    if (definition.includeCoil)
    {
        if (definition.coilHeight + 2 * definition.coilClearance > hSlot)
            throw regenError("The coil does not fit: coil height plus clearances exceeds the slot height.", ["coilHeight", "slotHeight"]);
        if (2 * definition.coilClearance >= wSlot)
            throw regenError("The coil clearance is too large for the slot width.", ["coilClearance", "slotWidth"]);
    }
    if (rotary)
    {
        if (xMax > 0.7 * layout.radius)
            throw regenError("Too few pole pairs for this air-gap radius: the core elements are wider than the machine.", ["rotaryPolePairs", "airGapRadius"]);
        if (definition.innerStator && layout.radius <= zTop)
            throw regenError("For an inner stator the air-gap radius must exceed the stator height.", ["airGapRadius"]);
    }

    // ----------------------------------------- pole-face trim setup
    // In a ring, prismatic cores have flat pole faces. When trimming, the legs are
    // built slightly long (down to zb) and then cut back to the air-gap cylinder.
    const margin = 0.05 * tau;
    const doTrim = rotary && trimmable && definition.trimPoleFaces;
    var zb = zero;
    if (doTrim)
    {
        if (layout.sign > 0)
            zb = -(layout.radius - sqrt(layout.radius * layout.radius - xMax * xMax) + margin);
        else
            zb = -margin;
    }

    // ------------------------------------------------ pole positions
    var evens = [];
    var odds = [];
    var mids = [];
    for (var k = 0; k < polePairs; k += 1)
    {
        evens = append(evens, 2 * k);
        odds = append(odds, 2 * k + 1);
        mids = append(mids, 2 * k + 0.5);
    }

    // --------------------------------------------------------- cores
    const coresId = id + "cores";

    if (coreType == TfmCoreType.U_CORE || coreType == TfmCoreType.UI_CORE)
    {
        // Fig. 4a: U-shaped cores at every second pole pitch, open towards the air gap.
        const uSeed = coresId + "uSeed";
        tfmPrism(context, uSeed, tfmCsYZ(-half), [
                    vector(-hw, zb),
                    vector(-wSlot / 2, zb),
                    vector(-wSlot / 2, hSlot),
                    vector(wSlot / 2, hSlot),
                    vector(wSlot / 2, zb),
                    vector(hw, zb),
                    vector(hw, zTop),
                    vector(-hw, zTop)
                ], t);
        tfmPlace(context, coresId + "uPlace", tfmSolids(uSeed), evens, layout);

        if (coreType == TfmCoreType.UI_CORE)
        {
            // Fig. 4b: trapezoidal I-bridge on the pole pitches between the U-cores.
            const hBridge = definition.bridgeHeight;
            const topHalf = definition.bridgeTopRatio * wSlot / 2;
            if (topHalf >= hw)
                throw regenError("The I-bridge top must be narrower than the core.", ["bridgeTopRatio"]);
            if (definition.includeCoil && hBridge > hSlot - definition.coilHeight - 2 * definition.coilClearance)
                throw regenError("The I-bridge collides with the coil: reduce the bridge height or the coil height.", ["bridgeHeight", "coilHeight"]);
            if (hBridge >= hSlot)
                throw regenError("The I-bridge must be lower than the slot.", ["bridgeHeight"]);

            const iSeed = coresId + "iSeed";
            tfmPrism(context, iSeed, tfmCsYZ(-half), [
                        vector(-hw, zb),
                        vector(hw, zb),
                        vector(hw, zero),
                        vector(topHalf, hBridge),
                        vector(-topHalf, hBridge),
                        vector(-hw, zero)
                    ], t);
            tfmPlace(context, coresId + "iPlace", tfmSolids(iSeed), odds, layout);
        }
    }
    else if (coreType == TfmCoreType.TR_CORE)
    {
        // Fig. 17: one continuous U-shaped ring holds the coil, and teeth stand on both side
        // walls, one per pole pair on each wall: aligned, or with the back wall one pole pitch
        // later (staggered, for a rotor with one magnet row); every second tooth carries the
        // pole shift.
        // Straight-cut teeth: each tooth reaches up to the slot height, so its flat end lies
        // inside the wall and the union is one solid per phase. Arched valleys: the walls
        // start at the air gap and the space between two teeth is cut away under an arch.
        const hTooth = definition.ringToothHeight;
        const arched = definition.archedValleys;
        const staggered = definition.staggeredTeeth;
        if (hTooth >= hSlot)
            throw regenError("The ring tooth height must be smaller than the slot height.", ["ringToothHeight", "slotHeight"]);
        if (!arched && rotary && layout.sign > 0 && sqrt((layout.radius + hSlot) * (layout.radius + hSlot) + half * half) > layout.radius + zTop)
            throw regenError("The yoke is too thin to cover the tooth ends.", ["yokeHeight"]);

        if (!arched)
        {
            const teethA = coresId + "trSeedA"; // front wall (-Y)
            tfmBox(context, teethA, -half, half, -hw, -wSlot / 2, zb, hSlot);
            tfmPlace(context, coresId + "trPlaceA", tfmSolids(teethA), evens, layout);
            const teethB = coresId + "trSeedB"; // back wall (+Y)
            tfmBox(context, teethB, -half, half, wSlot / 2, hw, zb, hSlot);
            tfmPlace(context, coresId + "trPlaceB", tfmSolids(teethB), staggered ? odds : evens, layout);
        }

        const hWall = arched ? zero : hTooth; // height above the air gap where the walls start
        const yWalls = [[-hw, -wSlot / 2], [wSlot / 2, hw]];
        if (rotary)
        {
            const rTooth = layout.radius + layout.sign * hWall;
            const rSlot = layout.radius + layout.sign * hSlot;
            const rTop = layout.radius + layout.sign * zTop;
            for (var ph = 0; ph < layout.phases; ph += 1)
            {
                const lift = ph * layout.phasePitch;
                for (var w = 0; w < 2; w += 1)
                    tfmRing(context, coresId + ("trWall" ~ w ~ "ph" ~ ph), min(rTooth, rSlot), max(rTooth, rSlot),
                        yWalls[w][0] + lift, yWalls[w][1] + lift);
                tfmRing(context, coresId + ("trYoke" ~ ph), min(rSlot, rTop), max(rSlot, rTop), -hw + lift, hw + lift);
            }
        }
        else
        {
            const x0 = -tau / 2;
            const x1 = (2 * polePairs - 0.5) * tau;
            for (var w = 0; w < 2; w += 1)
                tfmBox(context, coresId + ("trWall" ~ w), x0, x1, yWalls[w][0], yWalls[w][1], hWall, hSlot);
            tfmBox(context, coresId + "trYoke", x0, x1, -hw, hw, hSlot, zTop);
        }
        opBoolean(context, coresId + "trUnion", {
                    "tools" : tfmSolids(coresId),
                    "operationType" : BooleanOperationType.UNION
                });

        if (arched)
        {
            // Valley k of a wall lies between its teeth k and k + 1, at pole positions 2k + o and
            // 2k + 2 + o (o = 1 on the back wall of a staggered ring; the odd tooth shifted):
            // centre 2k + 1 + o + shift / 2, width 2 + shift for even k, 2 - shift for odd k.
            // Each cutter stops at the coil mid-plane, so it cuts its own wall only.
            const valleysId = id + "valleys";
            const shift = layout.shift;
            const unshifted = mergeMaps(layout, { "shift" : 0 }); // the centres already contain the shift
            const overshoot = layout.phases > 1 ? definition.phaseSpacing / 4 : margin;
            const count = rotary ? polePairs : polePairs - 1;
            const wallRanges = [[-hw - overshoot, zero], [zero, hw + overshoot]];
            const wallOffsets = [0, staggered ? 1 : 0];
            for (var wall = 0; wall < 2; wall += 1)
            {
                for (var parity = 0; parity < 2; parity += 1)
                {
                    var centres = [];
                    for (var k = parity; k < count; k += 2)
                        centres = append(centres, 2 * k + 1 + wallOffsets[wall] + shift / 2);
                    if (size(centres) > 0)
                    {
                        const seedId = valleysId + ("seed" ~ wall ~ parity);
                        tfmValleyCutter(context, seedId, layout, parity == 0 ? 2 + shift : 2 - shift, half, hTooth,
                            wallRanges[wall][0], wallRanges[wall][1]);
                        tfmPlace(context, valleysId + ("place" ~ wall ~ parity), tfmSolids(seedId), centres, unshifted);
                    }
                }
            }
            if (count > 0)
                opBoolean(context, id + "valleyCut", {
                            "tools" : tfmSolids(valleysId),
                            "targets" : tfmSolids(coresId),
                            "operationType" : BooleanOperationType.SUBTRACTION
                        });
        }
    }
    else if (coreType == TfmCoreType.C_CORE)
    {
        // Fig. 4c: the rotor runs between the two legs (two air-gap surfaces). The legs
        // sit one pole pitch apart along the motion direction, joined by a skewed yoke.
        const cSeed = coresId + "cSeed";
        const xa = -tau / 2;
        const xb = tau / 2;
        const yk = definition.skewFraction * wSlot / 2;

        tfmBox(context, cSeed + "legA", xa - half, xa + half, -hw, -wSlot / 2, zero, zTop);
        tfmBox(context, cSeed + "legB", xb - half, xb + half, wSlot / 2, hw, zero, zTop);
        tfmPrism(context, cSeed + "yoke", tfmCsXY(hSlot), [
                    vector(xa - half, -hw),
                    vector(xa + half, -hw),
                    vector(xa + half, -yk),
                    vector(xb + half, yk),
                    vector(xb + half, hw),
                    vector(xb - half, hw),
                    vector(xb - half, yk),
                    vector(xa - half, -yk)
                ], hYoke);
        opBoolean(context, cSeed + "union", {
                    "tools" : tfmSolids(cSeed),
                    "operationType" : BooleanOperationType.UNION
                });
        tfmPlace(context, coresId + "cPlace", tfmSolids(cSeed), mids, layout);
    }
    else if (coreType == TfmCoreType.CP_CORE)
    {
        // Fig. 4d: an O-shaped frame on every pole pitch. Each frame carries one wedge
        // shaped claw that spans the air-gap width; the claw root alternates between
        // the two side walls. Diagonal yoke links tie neighbouring frames together.
        const zc = definition.clawRootHeight;
        const zt = definition.clawTipHeight;
        const gap = definition.clawTipGap;
        if (gap >= wSlot)
            throw regenError("The claw tip gap must be smaller than the slot width.", ["clawTipGap"]);

        const signs = [1, -1];
        for (var i = 0; i < 2; i += 1)
        {
            const s = signs[i];
            const frameSeed = coresId + ("cpSeed" ~ i);
            tfmPrism(context, frameSeed, tfmCsYZ(-half), [
                        vector(-s * hw, zb),
                        vector(s * (wSlot / 2 - gap), zb),
                        vector(s * (wSlot / 2 - gap), zt),
                        vector(-s * wSlot / 2, zc),
                        vector(-s * wSlot / 2, zWindowTop),
                        vector(s * wSlot / 2, zWindowTop),
                        vector(s * wSlot / 2, zb),
                        vector(s * hw, zb),
                        vector(s * hw, zTop),
                        vector(-s * hw, zTop)
                    ], t);
            tfmPlace(context, coresId + ("cpPlace" ~ i), tfmSolids(frameSeed), i == 0 ? evens : odds, layout);
        }

        // Links run from the +Y end of frame j to the -Y end of frame j + 1 and reach
        // the mid-planes of both frames so that the union is robust.
        const zMid = (zWindowTop + zTop) / 2;
        var hs = tau / 2;
        if (rotary)
            hs = (layout.radius + layout.sign * zMid) * sin(layout.poleAngle / 2);
        var linkPositions = [];
        const linkCount = rotary ? 2 * polePairs : 2 * polePairs - 1;
        for (var j = 0; j < linkCount; j += 1)
            linkPositions = append(linkPositions, j + 0.5);

        const linkSeed = coresId + "cpLinkSeed";
        tfmPrism(context, linkSeed, tfmCsXY(zWindowTop), [
                    vector(-hs, hw),
                    vector(-hs, hw - wLeg),
                    vector(hs, -hw),
                    vector(hs, -hw + wLeg)
                ], hYoke);
        tfmPlace(context, coresId + "cpLinkPlace", tfmSolids(linkSeed), linkPositions, layout);

        opBoolean(context, coresId + "cpUnion", {
                    "tools" : tfmSolids(coresId),
                    "operationType" : BooleanOperationType.UNION
                });
    }
    else if (coreType == TfmCoreType.E_CORE)
    {
        // Fig. 4e: three legs and two coils. The middle leg sits one pole pitch away
        // from the outer legs, so the yoke is a chevron when seen from above.
        const eSeed = coresId + "eSeed";
        const wMid = definition.midLegWidth;
        const xo = -tau / 2; // outer legs
        const xm = tau / 2; // middle leg
        const yc = wMid / 2 + wSlot / 2; // window centre
        const ya = yc + definition.skewFraction * wSlot / 2;
        const yb = yc - definition.skewFraction * wSlot / 2;

        tfmBox(context, eSeed + "legA", xo - half, xo + half, -hw, -hw + wLeg, zb, zTop);
        tfmBox(context, eSeed + "legB", xo - half, xo + half, hw - wLeg, hw, zb, zTop);
        tfmBox(context, eSeed + "legM", xm - half, xm + half, -wMid / 2, wMid / 2, zb, zTop);
        tfmPrism(context, eSeed + "yoke", tfmCsXY(hSlot), [
                    vector(xo - half, -hw),
                    vector(xo + half, -hw),
                    vector(xo + half, -ya),
                    vector(xm + half, -yb),
                    vector(xm + half, yb),
                    vector(xo + half, ya),
                    vector(xo + half, hw),
                    vector(xo - half, hw),
                    vector(xo - half, ya),
                    vector(xm - half, yb),
                    vector(xm - half, -yb),
                    vector(xo - half, -ya)
                ], hYoke);
        opBoolean(context, eSeed + "union", {
                    "tools" : tfmSolids(eSeed),
                    "operationType" : BooleanOperationType.UNION
                });
        tfmPlace(context, coresId + "ePlace", tfmSolids(eSeed), mids, layout);
    }
    else
    {
        // Fig. 4f: plate with a coil window, a tooth facing the rotor from above, and
        // a leg that passes the rotor and returns underneath it as a lower limb.
        const hT = definition.zToothHeight;
        const gR = definition.zRotorGap;
        const yT1 = wSlot / 2 - definition.zSlotGap; // tooth face next to the leg
        const yT0 = yT1 - definition.zToothWidth;
        if (definition.zSlotGap >= wSlot)
            throw regenError("The tooth to leg gap must be smaller than the slot width.", ["zSlotGap"]);
        if (yT0 <= -hw)
            throw regenError("The tooth is too wide for this core.", ["zToothWidth"]);
        const zLimb = -gR - hYoke;

        const zSeed = coresId + "zSeed";
        tfmPrism(context, zSeed, tfmCsYZ(-half), [
                    vector(-hw, zLimb),
                    vector(hw, zLimb),
                    vector(hw, zTop),
                    vector(-hw, zTop),
                    vector(-hw, hT / 2),
                    vector(yT0, hT / 2),
                    vector(yT0, zero),
                    vector(yT1, zero),
                    vector(yT1, hT),
                    vector(-wSlot / 2, hT),
                    vector(-wSlot / 2, zWindowTop),
                    vector(wSlot / 2, zWindowTop),
                    vector(wSlot / 2, -gR),
                    vector(-hw, -gR)
                ], t);
        tfmPlace(context, coresId + "zPlace", tfmSolids(zSeed), evens, layout);
    }

    // ------------------------------------------------ pole-face trim
    if (doTrim)
    {
        const trimId = id + "trim";
        const yHalf = hw + tau;
        if (layout.sign > 0)
            tfmRing(context, trimId + "tool", layout.radius + zb - margin, layout.radius, -yHalf, yHalf + phaseSpan);
        else
            tfmRing(context, trimId + "tool", layout.radius, layout.radius + xMax + 2 * margin, -yHalf, yHalf + phaseSpan);
        opBoolean(context, trimId + "cut", {
                    "tools" : tfmSolids(trimId + "tool"),
                    "targets" : tfmSolids(coresId),
                    "operationType" : BooleanOperationType.SUBTRACTION
                });
    }

    setProperty(context, { "entities" : tfmSolids(coresId), "propertyType" : PropertyType.NAME, "value" : "TFM core" });
    setProperty(context, { "entities" : tfmSolids(coresId), "propertyType" : PropertyType.APPEARANCE, "value" : color(0.62, 0.62, 0.64) });

    // ---------------------------------------------------------- coil
    if (definition.includeCoil)
    {
        const coilId = id + "coil";
        const z1 = zWindowTop - definition.coilClearance;
        const z0 = z1 - definition.coilHeight;
        for (var c = 0; c < size(coilCenters); c += 1)
        {
            const y0 = coilCenters[c] - wSlot / 2 + definition.coilClearance;
            const y1 = coilCenters[c] + wSlot / 2 - definition.coilClearance;
            if (rotary)
            {
                const ra = layout.radius + layout.sign * z0;
                const rb = layout.radius + layout.sign * z1;
                for (var ph = 0; ph < layout.phases; ph += 1)
                {
                    const lift = ph * layout.phasePitch;
                    tfmRing(context, coilId + ("ring" ~ c ~ "ph" ~ ph), layout.sign > 0 ? ra : rb, layout.sign > 0 ? rb : ra, y0 + lift, y1 + lift);
                }
            }
            else
            {
                tfmPrism(context, coilId + ("bar" ~ c), tfmCsYZ(-tau / 2), [
                            vector(y0, z0),
                            vector(y1, z0),
                            vector(y1, z1),
                            vector(y0, z1)
                        ], 2 * polePairs * tau);
            }
        }
        setProperty(context, { "entities" : tfmSolids(coilId), "propertyType" : PropertyType.NAME, "value" : "TFM coil" });
        setProperty(context, { "entities" : tfmSolids(coilId), "propertyType" : PropertyType.APPEARANCE, "value" : color(0.80, 0.42, 0.20) });
    }
}

const TFM_STATOR_DEFAULTS = {
            "coreType" : TfmCoreType.U_CORE,
            "arrangement" : TfmArrangement.LINEAR,
            "polePitch" : 10 * millimeter,
            "linearPolePairs" : 2,
            "airGapRadius" : 60 * millimeter,
            "rotaryPolePairs" : 16,
            "innerStator" : false,
            "trimPoleFaces" : true,
            "phases" : 1,
            "phaseSpacing" : 1 * millimeter,
            "poleShift" : 0 * degree,
            "toothSpan" : 0.8,
            "legWidth" : 10 * millimeter,
            "slotWidth" : 20 * millimeter,
            "slotHeight" : 25 * millimeter,
            "yokeHeight" : 10 * millimeter,
            "bridgeHeight" : 6 * millimeter,
            "bridgeTopRatio" : 0.8,
            "skewFraction" : 0.6,
            "clawRootHeight" : 8 * millimeter,
            "clawTipHeight" : 2 * millimeter,
            "clawTipGap" : 1 * millimeter,
            "midLegWidth" : 20 * millimeter,
            "zToothHeight" : 12 * millimeter,
            "zToothWidth" : 10 * millimeter,
            "zSlotGap" : 2 * millimeter,
            "zRotorGap" : 6 * millimeter,
            "ringToothHeight" : 8 * millimeter,
            "archedValleys" : false,
            "staggeredTeeth" : false,
            "includeCoil" : true,
            "coilHeight" : 12 * millimeter,
            "coilClearance" : 1 * millimeter
        };

// --------------------------------------------------------------- helpers

/** Solid bodies created by any operation below `id`. */
function tfmSolids(id is Id) returns Query
{
    return qBodyType(qCreatedBy(id, EntityType.BODY), BodyType.SOLID);
}

/** Sketch frame in the local Y-Z plane at X = x0; extrusion runs along +X. */
function tfmCsYZ(x0 is ValueWithUnits) returns CoordSystem
{
    return coordSystem(vector(x0, 0 * meter, 0 * meter), vector(0, 1, 0), vector(1, 0, 0));
}

/** Sketch frame in the local X-Y plane at Z = z0; extrusion runs along +Z. */
function tfmCsXY(z0 is ValueWithUnits) returns CoordSystem
{
    return coordSystem(vector(0 * meter, 0 * meter, z0), vector(1, 0, 0), vector(0, 0, 1));
}

/**
 * Extrudes the closed polygon `points` (2D, in the XY plane of `cs`) by `depth` along the Z axis of `cs`.
 * Consecutive duplicate points are dropped, so callers may pass degenerate corners.
 */
function tfmPrism(context is Context, id is Id, cs is CoordSystem, points is array, depth is ValueWithUnits)
{
    var pts = [];
    for (var point in points)
    {
        if (size(pts) == 0 || !tolerantEquals(point, pts[size(pts) - 1]))
            pts = append(pts, point);
    }
    if (size(pts) > 1 && tolerantEquals(pts[0], pts[size(pts) - 1]))
        pts = resize(pts, size(pts) - 1);
    pts = append(pts, pts[0]);

    const sketch = newSketchOnPlane(context, id + "sketch", { "sketchPlane" : plane(cs) });
    skPolyline(sketch, "profile", { "points" : pts });
    skSolve(sketch);
    opExtrude(context, id + "extrude", {
                "entities" : qSketchRegion(id + "sketch"),
                "direction" : cs.zAxis,
                "endBound" : BoundingType.BLIND,
                "endDepth" : depth
            });
    opDeleteBodies(context, id + "deleteSketch", { "entities" : qCreatedBy(id + "sketch", EntityType.BODY) });
}

/**
 * Seed solid that removes one arched valley of the toothed ring, in the frame of pole position 0,
 * for a valley `du` pole pitches wide between tooth centres. The arch ends at the top corners of
 * the two teeth, which lie on the air-gap circle so that each tooth keeps its top width 2 * half,
 * and its deepest point is at `depth` on the valley centre line. If the valley is deeper than half
 * its width, the bottom is a half circle and the sides are straight. The solid reaches past the
 * corners into the air gap, and from yMin to yMax along the local Y (machine) axis: one side wall,
 * a little beyond it but less than half the phase spacing, so that it does not touch the next phase.
 */
function tfmValleyCutter(context is Context, id is Id, layout is map, du is number, half is ValueWithUnits,
    depth is ValueWithUnits, yMin is ValueWithUnits, yMax is ValueWithUnits)
{
    var xc = du * layout.tau / 2 - half;
    var zc = 0 * meter;
    if (layout.rotary)
    {
        const phi = du * layout.poleAngle / 2 - asin(half / layout.radius);
        xc = layout.radius * sin(phi);
        zc = layout.sign * (layout.radius * cos(phi) - layout.radius);
    }
    if (xc <= 0 * meter)
        throw regenError("The teeth are too wide for arched valleys.", ["toothSpan", "archedValleys"]);
    const margin = 0.5 * layout.tau;

    // Sketch in the local X-Z plane: sketch (u, v) is local (X, -Z). Extrusion runs along +Y.
    const cs = coordSystem(vector(0 * meter, yMin, 0 * meter), vector(1, 0, 0), vector(0, 1, 0));
    const sketch = newSketchOnPlane(context, id + "sketch", { "sketchPlane" : plane(cs) });
    const a = vector(-xc, -zc);
    const b = vector(xc, -zc);
    const bottom = vector(0 * meter, -depth);
    if (depth - zc <= xc)
    {
        skArc(sketch, "arch", { "start" : a, "mid" : bottom, "end" : b });
    }
    else
    {
        const a2 = vector(-xc, xc - depth);
        const b2 = vector(xc, xc - depth);
        skLineSegment(sketch, "sideA", { "start" : a, "end" : a2 });
        skArc(sketch, "arch", { "start" : a2, "mid" : bottom, "end" : b2 });
        skLineSegment(sketch, "sideB", { "start" : b2, "end" : b });
    }
    const b3 = vector(xc, margin - zc);
    const a3 = vector(-xc, margin - zc);
    skLineSegment(sketch, "out", { "start" : b, "end" : b3 });
    skLineSegment(sketch, "across", { "start" : b3, "end" : a3 });
    skLineSegment(sketch, "back", { "start" : a3, "end" : a });
    skSolve(sketch);
    opExtrude(context, id + "extrude", {
                "entities" : qSketchRegion(id + "sketch"),
                "direction" : cs.zAxis,
                "endBound" : BoundingType.BLIND,
                "endDepth" : yMax - yMin
            });
    opDeleteBodies(context, id + "deleteSketch", { "entities" : qCreatedBy(id + "sketch", EntityType.BODY) });
}

/** Axis-aligned box in the local frame. */
function tfmBox(context is Context, id is Id, x0 is ValueWithUnits, x1 is ValueWithUnits,
    y0 is ValueWithUnits, y1 is ValueWithUnits, z0 is ValueWithUnits, z1 is ValueWithUnits)
{
    tfmPrism(context, id, tfmCsXY(z0), [
                vector(x0, y0),
                vector(x1, y0),
                vector(x1, y1),
                vector(x0, y1)
            ], z1 - z0);
}

/** Ring around the world Z axis: radius from rMin to rMax, axial extent from yMin to yMax. */
function tfmRing(context is Context, id is Id, rMin is ValueWithUnits, rMax is ValueWithUnits,
    yMin is ValueWithUnits, yMax is ValueWithUnits)
{
    // Sketch plane through the machine axis: sketch (u, v) maps to world (u, 0, v).
    const sketchPlane = plane(vector(0, 0, 0) * meter, vector(0, -1, 0), vector(1, 0, 0));
    const sketch = newSketchOnPlane(context, id + "sketch", { "sketchPlane" : sketchPlane });
    skRectangle(sketch, "section", {
                "firstCorner" : vector(rMin, yMin),
                "secondCorner" : vector(rMax, yMax)
            });
    skSolve(sketch);
    opRevolve(context, id + "revolve", {
                "entities" : qSketchRegion(id + "sketch"),
                "axis" : line(vector(0, 0, 0) * meter, vector(0, 0, 1)),
                "angleForward" : 2 * PI * radian,
                "angleBack" : 0 * radian
            });
    opDeleteBodies(context, id + "deleteSketch", { "entities" : qCreatedBy(id + "sketch", EntityType.BODY) });
}

/**
 * Transform from the local element frame to the world for pole position `u`, counted in pole pitches.
 * Linear: translation along X. Rotary: X becomes tangential, Z radial, Y the machine axis.
 */
function tfmPoleTransform(layout is map, u is number) returns Transform
{
    if (!layout.rotary)
        return transform(vector(u * layout.tau, 0 * meter, 0 * meter));

    const theta = u * layout.poleAngle;
    const radial = vector(cos(theta), sin(theta), 0);
    const tangent = vector(-sin(theta), cos(theta), 0);
    return toWorld(coordSystem(radial * layout.radius, tangent, radial * layout.sign));
}

/**
 * Copies the seed bodies to every pole position in `positions`, for every phase, then removes the seeds.
 * Every second position gets the extra pole shift. Phase k is moved k phase pitches along the
 * machine axis and turned by k phase steps.
 */
function tfmPlace(context is Context, id is Id, seeds is Query, positions is array, layout is map)
{
    var transforms = [];
    var names = [];
    for (var ph = 0; ph < layout.phases; ph += 1)
    {
        const lift = transform(vector(0 * meter, 0 * meter, ph * layout.phasePitch));
        for (var i = 0; i < size(positions); i += 1)
        {
            const u = positions[i] + ((i % 2 == 1) ? layout.shift : 0) + ph * layout.phaseStep;
            transforms = append(transforms, lift * tfmPoleTransform(layout, u));
            names = append(names, "ph" ~ ph ~ "pole" ~ i);
        }
    }
    opPattern(context, id + "pattern", {
                "entities" : seeds,
                "transforms" : transforms,
                "instanceNames" : names
            });
    opDeleteBodies(context, id + "deleteSeed", { "entities" : seeds });
}

/**
 * TFM rotor
 *
 * Parametric permanent-magnet rotor, as an inrunner (rotor inside the stator, magnets on the
 * outside) or an outrunner (rotor around the stator, magnets on the inside). The rotor axis
 * is the world Z axis and the stack of the first phase is centred on Z = 0, which matches the
 * "Rotary ring" layout of the TFM stator feature.
 *
 * Rotor types:
 *   - Interleaved N-S surface magnets on a back iron.
 *   - Halbach array: every pole is split into segments whose magnetisation rotates so that
 *     the field is concentrated on the air-gap side (towards the stator).
 *   - Flux concentrating: tangentially magnetised spoke magnets interleaved with iron poles.
 *   - Axially magnetised ring between toothed discs (B. Kaiser and N. Parspour, "Transverse
 *     Flux Machine - A Review", IEEE Access, vol. 10, 2022, Fig. 3c): per phase two soft-iron
 *     discs, one at each axial end of the stack, each with poles / 2 teeth on the air-gap side,
 *     and one ring magnet between them. The teeth of the second disc sit one pole pitch after
 *     those of the first, so the first disc (-Z end) is all north poles and the second all
 *     south poles; the magnet is magnetised along -Z. For this type "Magnet thickness" is the
 *     radial height of the teeth, "Magnet arc / pole pitch" the tooth arc, and "Gap between
 *     rows" the axial length of the ring magnet; each disc is (stack length - gap) / 2 thick.
 *     Discs and magnet reach from the tooth root to the shaft (inrunner) or to the outer
 *     diameter (outrunner), so there is no separate back iron.
 *
 * Phases: "Number of phases" repeats the whole rotor ring along +Z. "Stack length" is the
 * length of one phase and phase k is moved k * (stack length + phase spacing), without any
 * rotation: the electrical phase shift is made in the stator. The shaft runs through all
 * phases; the end cap stays at the -Z end.
 *
 * Magnetisation convention: the pole centred on the +X axis is a north pole, meaning flux
 * leaves the rotor into the air gap. For a magnet centred at electrical angle e, the
 * magnetisation direction measured from the local radial direction is -e for an inrunner
 * and e + 180 degrees for an outrunner. Magnets are coloured by electrical angle
 * (red = north pole facing the gap, green = south pole facing the gap, yellow / blue =
 * tangential) and an optional sketch on the end face of the first phase draws one arrow per
 * magnet (not for the axially magnetised type).
 */

export enum TfmRotorConfiguration
{
    annotation { "Name" : "Inrunner (rotor inside the stator)" }
    INRUNNER,
    annotation { "Name" : "Outrunner (rotor around the stator)" }
    OUTRUNNER
}

export enum TfmRotorType
{
    annotation { "Name" : "Interleaved N-S surface magnets" }
    SURFACE,
    annotation { "Name" : "Halbach array" }
    HALBACH,
    annotation { "Name" : "Flux concentrating (magnets interleaved with iron poles)" }
    FLUX_CONCENTRATING,
    annotation { "Name" : "Axially magnetised ring between toothed discs" }
    AXIAL
}

// ---------------------------------------------------------------- bounds

const ROTOR_OD_BOUNDS = {
            (meter) : [1e-4, 0.118, 500],
            (centimeter) : 11.8,
            (millimeter) : 118.0,
            (inch) : 4.65,
            (foot) : 0.39,
            (yard) : 0.13
        } as LengthBoundSpec;

const ROTOR_SHAFT_BOUNDS = {
            (meter) : [0, 0.030, 500],
            (centimeter) : 3.0,
            (millimeter) : 30.0,
            (inch) : 1.2,
            (foot) : 0.1,
            (yard) : 0.033
        } as LengthBoundSpec;

const ROTOR_STACK_BOUNDS = {
            (meter) : [1e-5, 0.040, 500],
            (centimeter) : 4.0,
            (millimeter) : 40.0,
            (inch) : 1.6,
            (foot) : 0.13,
            (yard) : 0.044
        } as LengthBoundSpec;

const ROTOR_PHASE_SPACING_BOUNDS = {
            (meter) : [1e-5, 0.001, 500],
            (centimeter) : 0.1,
            (millimeter) : 1.0,
            (inch) : 0.04,
            (foot) : 0.003,
            (yard) : 0.001
        } as LengthBoundSpec;

const ROTOR_MAGNET_BOUNDS = {
            (meter) : [1e-5, 0.005, 500],
            (centimeter) : 0.5,
            (millimeter) : 5.0,
            (inch) : 0.2,
            (foot) : 0.016,
            (yard) : 0.0055
        } as LengthBoundSpec;

const ROTOR_FC_HEIGHT_BOUNDS = {
            (meter) : [1e-5, 0.012, 500],
            (centimeter) : 1.2,
            (millimeter) : 12.0,
            (inch) : 0.5,
            (foot) : 0.04,
            (yard) : 0.013
        } as LengthBoundSpec;

const ROTOR_FC_WIDTH_BOUNDS = {
            (meter) : [1e-5, 0.004, 500],
            (centimeter) : 0.4,
            (millimeter) : 4.0,
            (inch) : 0.16,
            (foot) : 0.013,
            (yard) : 0.0044
        } as LengthBoundSpec;

const ROTOR_ROW_GAP_BOUNDS = {
            (meter) : [0, 0.020, 500],
            (centimeter) : 2.0,
            (millimeter) : 20.0,
            (inch) : 0.8,
            (foot) : 0.065,
            (yard) : 0.022
        } as LengthBoundSpec;

const ROTOR_SHAFT_EXT_BOUNDS = {
            (meter) : [0, 0.020, 500],
            (centimeter) : 2.0,
            (millimeter) : 20.0,
            (inch) : 0.8,
            (foot) : 0.065,
            (yard) : 0.022
        } as LengthBoundSpec;

const ROTOR_OUT_ID_BOUNDS = {
            (meter) : [1e-4, 0.122, 500],
            (centimeter) : 12.2,
            (millimeter) : 122.0,
            (inch) : 4.8,
            (foot) : 0.4,
            (yard) : 0.133
        } as LengthBoundSpec;

const ROTOR_OUT_OD_BOUNDS = {
            (meter) : [1e-4, 0.160, 500],
            (centimeter) : 16.0,
            (millimeter) : 160.0,
            (inch) : 6.3,
            (foot) : 0.525,
            (yard) : 0.175
        } as LengthBoundSpec;

const ROTOR_CAP_BORE_BOUNDS = {
            (meter) : [0, 0.010, 500],
            (centimeter) : 1.0,
            (millimeter) : 10.0,
            (inch) : 0.4,
            (foot) : 0.033,
            (yard) : 0.011
        } as LengthBoundSpec;

const ROTOR_POLES_BOUNDS = { (unitless) : [2, 32, 1000] } as IntegerBoundSpec;
const ROTOR_SEGMENTS_BOUNDS = { (unitless) : [2, 2, 12] } as IntegerBoundSpec;
const ROTOR_ROWS_BOUNDS = { (unitless) : [1, 1, 12] } as IntegerBoundSpec;
const ROTOR_PHASES_BOUNDS = { (unitless) : [1, 1, 6] } as IntegerBoundSpec;
const ROTOR_ARC_BOUNDS = { (unitless) : [0.1, 0.85, 1.0] } as RealBoundSpec;

// --------------------------------------------------------------- feature

/** The "TFM rotor" feature, as a function: fields not given take the defaults of the feature. */
function tfmInrunnerRotor(context is Context, id is Id, given is map)
{
    const definition = mergeMaps(TFM_ROTOR_DEFAULTS, given);
    const rotorType = definition.rotorType;
    const outrunner = definition.configuration == TfmRotorConfiguration.OUTRUNNER;
    const fluxConcentrating = rotorType == TfmRotorType.FLUX_CONCENTRATING;
    const axial = rotorType == TfmRotorType.AXIAL;
    const poles = definition.poles;
    if (poles % 2 != 0)
        throw regenError("The number of poles must be even.", ["poles"]);

    const stack = definition.stackLength; // length of one phase
    const polePitch = 2 * PI / poles; // mechanical angle of one pole, in radians
    const zero = 0 * meter;
    const z0 = -stack / 2;
    const zAxis = line(vector(0, 0, 0) * meter, vector(0, 0, 1));

    // -------------------------------------------------------- phases
    // Phase k repeats the rotor ring k phase pitches further along +Z, without rotation:
    // the electrical phase shift is made in the stator.
    const phases = definition.phases;
    const phasePitch = stack + (phases > 1 ? definition.phaseSpacing : zero);
    const totalLength = (phases - 1) * phasePitch + stack; // from the -Z end of the first phase to the +Z end of the last

    // ---------------------------------------------------- axial rows
    const rows = axial ? 1 : definition.magnetRows;
    const rowGap = rows > 1 ? definition.rowGap : zero;
    const alternate = rows > 1 && definition.alternateRows;
    const rowWidth = (stack - (rows - 1) * rowGap) / rows;
    if (rowWidth <= 1e-6 * meter)
        throw regenError("The row gaps use up the whole stack length.", ["rowGap", "magnetRows", "stackLength"]);

    // ------------------------------------------------- magnet layout
    // For the axially magnetised type hm is the radial height of the disc teeth.
    const hm = fluxConcentrating ? definition.fcMagnetHeight : definition.magnetThickness;

    // Radii: the magnets occupy ra..rb, the core (back iron, hub or housing) occupies coreIn..coreOut.
    // Inrunner: magnets outside, air gap at rb. Outrunner: magnets inside, air gap at ra.
    var ra = zero;
    var rb = zero;
    var coreIn = zero;
    var coreOut = zero;
    if (outrunner)
    {
        ra = definition.outrunnerInnerDiameter / 2;
        rb = ra + hm;
        coreIn = rb;
        coreOut = definition.outrunnerOuterDiameter / 2;
        if (coreOut <= rb + 1e-6 * meter)
            throw regenError("The magnets leave no room for the rotor housing: increase the outer diameter or reduce the magnet size.", ["outrunnerOuterDiameter", "outrunnerInnerDiameter"]);
    }
    else
    {
        rb = definition.outerDiameter / 2;
        ra = rb - hm;
        coreIn = definition.shaftDiameter / 2;
        coreOut = ra;
        if (ra <= coreIn + 1e-6 * meter)
            throw regenError("The magnets leave no room for the rotor core: reduce the magnet size or the shaft diameter.", ["outerDiameter", "shaftDiameter"]);
    }

    // Electrical angles (degrees) of the magnet centres inside one pole pair, and the
    // mechanical angle (radians) covered by one magnet (or by one disc tooth).
    var electricalAngles = [0, 180];
    var span = polePitch;
    var wm = zero; // tangential width of a spoke magnet
    if (rotorType == TfmRotorType.SURFACE || axial)
    {
        span = definition.magnetArcRatio * polePitch;
    }
    else if (rotorType == TfmRotorType.HALBACH)
    {
        const segments = definition.segmentsPerPole;
        span = polePitch / segments;
        electricalAngles = [];
        for (var k = 0; k < 2 * segments; k += 1)
            electricalAngles = append(electricalAngles, k * 180 / segments);
    }
    else
    {
        electricalAngles = [90, 270];
        wm = definition.fcMagnetWidth;
        if (wm >= ra * sin(polePitch / 2 * radian))
            throw regenError("The magnets are too wide for this pole count.", ["fcMagnetWidth", "poles"]);
    }

    if (axial)
    {
        // ------------------------------ toothed discs and ring magnet
        // Review paper, Fig. 3c. Disc 0 sits at the -Z end of the stack with a tooth on +X
        // (north), disc 1 at the +Z end with its teeth one pole pitch further (south).
        const magnetLength = definition.rowGap; // "Gap between rows" is the axial length of the ring magnet
        const discThickness = (stack - magnetLength) / 2;
        if (magnetLength <= 1e-6 * meter)
            throw regenError("The ring magnet needs an axial length: increase the gap between rows.", ["rowGap"]);
        if (discThickness <= 1e-6 * meter)
            throw regenError("The ring magnet uses up the whole stack length: reduce the gap between rows.", ["rowGap", "stackLength"]);

        // The disc bodies and the ring magnet fill the core region, the teeth the magnet region.
        // The tooth seed reaches half way into the disc body, so that the union is robust.
        const axialId = id + "axial";
        const seedId = axialId + "seed";
        const rMid = (coreIn + coreOut) / 2;
        const toothIn = outrunner ? ra : rMid;
        const toothOut = outrunner ? rMid : rb;
        const c = cos(span / 2 * radian);
        const s = sin(span / 2 * radian);
        rotorSector(context, seedId, z0, discThickness, toothIn, toothOut,
            vector(toothIn * c, toothIn * s), vector(toothOut * c, toothOut * s));

        const discNames = ["Rotor disc N", "Rotor disc S"];
        for (var ph = 0; ph < phases; ph += 1)
        {
            const zp = z0 + ph * phasePitch;
            for (var d = 0; d < 2; d += 1)
            {
                const lift = transform(vector(zero, zero, ph * phasePitch + d * (stack - discThickness)));
                var transforms = [];
                var names = [];
                for (var j = 0; j < poles / 2; j += 1)
                {
                    transforms = append(transforms, lift * rotationAround(zAxis, (2 * j + d) * polePitch * radian));
                    names = append(names, "tooth" ~ j);
                }
                const teethId = axialId + ("ph" ~ ph ~ "teeth" ~ d);
                opPattern(context, teethId, {
                            "entities" : tfmSolids(seedId),
                            "transforms" : transforms,
                            "instanceNames" : names
                        });
                const discId = axialId + ("ph" ~ ph ~ "disc" ~ d);
                const zd = zp + d * (stack - discThickness);
                tfmRing(context, discId, coreIn, coreOut, zd, zd + discThickness);
                const disc = qUnion([tfmSolids(discId), tfmSolids(teethId)]);
                opBoolean(context, axialId + ("ph" ~ ph ~ "union" ~ d), {
                            "tools" : disc,
                            "operationType" : BooleanOperationType.UNION
                        });
                setProperty(context, { "entities" : disc, "propertyType" : PropertyType.NAME, "value" : discNames[d] });
                setProperty(context, { "entities" : disc, "propertyType" : PropertyType.APPEARANCE, "value" : color(0.62, 0.62, 0.64) });
            }
            const magnetId = axialId + ("ph" ~ ph ~ "magnet");
            tfmRing(context, magnetId, coreIn, coreOut, zp + discThickness, zp + stack - discThickness);
            setProperty(context, { "entities" : tfmSolids(magnetId), "propertyType" : PropertyType.NAME, "value" : "Magnet (axial)" });
            setProperty(context, { "entities" : tfmSolids(magnetId), "propertyType" : PropertyType.APPEARANCE, "value" : color(0.80, 0.15, 0.15) });
        }
        // Operations that share a parent id must be consecutive, so the seed is deleted under axialId.
        opDeleteBodies(context, axialId + "deleteSeed", { "entities" : tfmSolids(seedId) });
    }
    else
    {
        // ------------------------------------------------- magnet seed
        const magnetsId = id + "magnets";
        const seedId = magnetsId + "seed";
        // The outline is bounded by the arcs ra and rb, so the magnet seats on the core without a gap.
        // Sector magnets have radial sides; spoke magnets have parallel sides wm apart.
        var innerX = zero;
        var innerY = zero;
        var outerX = zero;
        var outerY = zero;
        if (fluxConcentrating)
        {
            innerY = wm / 2;
            outerY = wm / 2;
            innerX = sqrt(ra * ra - wm * wm / 4);
            outerX = sqrt(rb * rb - wm * wm / 4);
        }
        else
        {
            const c = cos(span / 2 * radian);
            const s = sin(span / 2 * radian);
            innerX = ra * c;
            innerY = ra * s;
            outerX = rb * c;
            outerY = rb * s;
        }
        rotorSector(context, seedId, z0, rowWidth, ra, rb, vector(innerX, innerY), vector(outerX, outerY));

        // One pattern per magnetisation direction, so each group gets its own name and colour.
        for (var k = 0; k < size(electricalAngles); k += 1)
        {
            const beta = rotorMagnetAngle(electricalAngles[k], outrunner); // degrees from radial
            const offset = electricalAngles[k] / 180 * polePitch;
            var transforms = [];
            var names = [];
            for (var ph = 0; ph < phases; ph += 1)
            {
                for (var r = 0; r < rows; r += 1)
                {
                    const rowShift = (alternate && r % 2 == 1) ? polePitch : 0;
                    const lift = transform(vector(zero, zero, ph * phasePitch + r * (rowWidth + rowGap)));
                    for (var j = 0; j < poles / 2; j += 1)
                    {
                        const angle = (offset + 2 * j * polePitch + rowShift) * radian;
                        transforms = append(transforms, lift * rotationAround(zAxis, angle));
                        names = append(names, "ph" ~ ph ~ "r" ~ r ~ "p" ~ j);
                    }
                }
            }
            const groupId = magnetsId + ("group" ~ k);
            opPattern(context, groupId, {
                        "entities" : tfmSolids(seedId),
                        "transforms" : transforms,
                        "instanceNames" : names
                    });
            setProperty(context, { "entities" : tfmSolids(groupId), "propertyType" : PropertyType.NAME, "value" : rotorMagnetName(beta, outrunner) });
            setProperty(context, { "entities" : tfmSolids(groupId), "propertyType" : PropertyType.APPEARANCE, "value" : rotorMagnetColor((360 - electricalAngles[k]) % 360) });
        }
        // Operations that share a parent id must be consecutive, so the seed is deleted under magnetsId.
        opDeleteBodies(context, magnetsId + "deleteSeed", { "entities" : tfmSolids(seedId) });

        // --------------------------------------------- iron pole pieces
        if (fluxConcentrating)
        {
            const polesId = id + "polePieces";
            var rings = [];
            for (var ph = 0; ph < phases; ph += 1)
            {
                for (var r = 0; r < rows; r += 1)
                {
                    const zr = z0 + ph * phasePitch + r * (rowWidth + rowGap);
                    const ringId = polesId + ("ph" ~ ph ~ "ring" ~ r);
                    tfmRing(context, ringId, ra, rb, zr, zr + rowWidth);
                    rings = append(rings, tfmSolids(ringId));
                }
            }

            // Slot cutter: wider than the ring radially and as long as all phases together, so
            // every ring is split into separate poles.
            const slotId = polesId + "slot";
            const slotSketch = newSketchOnPlane(context, slotId + "sketch", {
                        "sketchPlane" : plane(vector(zero, zero, z0), vector(0, 0, 1), vector(1, 0, 0))
                    });
            skRectangle(slotSketch, "slot", {
                        "firstCorner" : vector(0.8 * ra, -wm / 2),
                        "secondCorner" : vector(rb + hm, wm / 2)
                    });
            skSolve(slotSketch);
            opExtrude(context, slotId + "extrude", {
                        "entities" : qSketchRegion(slotId + "sketch"),
                        "direction" : vector(0, 0, 1),
                        "endBound" : BoundingType.BLIND,
                        "endDepth" : totalLength
                    });
            opDeleteBodies(context, slotId + "deleteSketch", { "entities" : qCreatedBy(slotId + "sketch", EntityType.BODY) });

            var slotTransforms = [];
            var slotNames = [];
            for (var j = 0; j < poles; j += 1)
            {
                slotTransforms = append(slotTransforms, rotationAround(zAxis, (j + 0.5) * polePitch * radian));
                slotNames = append(slotNames, "slot" ~ j);
            }
            const cuttersId = polesId + "cutters";
            opPattern(context, cuttersId, {
                        "entities" : tfmSolids(slotId),
                        "transforms" : slotTransforms,
                        "instanceNames" : slotNames
                    });
            opDeleteBodies(context, polesId + "deleteSlotSeed", { "entities" : tfmSolids(slotId) });

            opBoolean(context, polesId + "cut", {
                        "tools" : tfmSolids(cuttersId),
                        "targets" : qUnion(rings),
                        "operationType" : BooleanOperationType.SUBTRACTION
                    });
            setProperty(context, { "entities" : tfmSolids(polesId), "propertyType" : PropertyType.NAME, "value" : "Rotor pole piece" });
            setProperty(context, { "entities" : tfmSolids(polesId), "propertyType" : PropertyType.APPEARANCE, "value" : color(0.55, 0.55, 0.57) });
        }

        // ------------------------------------------------------ core
        const coreId = id + "core";
        for (var ph = 0; ph < phases; ph += 1)
        {
            const zp = z0 + ph * phasePitch;
            tfmRing(context, coreId + ("ph" ~ ph), coreIn, coreOut, zp, zp + stack);
        }
        var coreName = "Rotor back iron";
        var coreColor = color(0.62, 0.62, 0.64);
        if (rotorType == TfmRotorType.HALBACH)
            coreName = outrunner ? "Rotor housing" : "Rotor hub";
        if (fluxConcentrating)
        {
            coreName = outrunner ? "Rotor housing (non-magnetic)" : "Rotor hub (non-magnetic)";
            coreColor = color(0.82, 0.82, 0.84);
        }
        setProperty(context, { "entities" : tfmSolids(coreId), "propertyType" : PropertyType.NAME, "value" : coreName });
        setProperty(context, { "entities" : tfmSolids(coreId), "propertyType" : PropertyType.APPEARANCE, "value" : coreColor });
    }

    // ----------------------------------------------------- shaft
    if (!outrunner && definition.includeShaft)
    {
        if (coreIn <= 1e-6 * meter)
            throw regenError("A shaft needs a shaft diameter larger than zero.", ["shaftDiameter"]);
        const shaftId = id + "shaft";
        const extension = definition.shaftExtension;
        // One shaft through all phases.
        tfmRing(context, shaftId, zero, coreIn, z0 - extension, z0 + totalLength + extension);
        setProperty(context, { "entities" : tfmSolids(shaftId), "propertyType" : PropertyType.NAME, "value" : "Shaft" });
        setProperty(context, { "entities" : tfmSolids(shaftId), "propertyType" : PropertyType.APPEARANCE, "value" : color(0.42, 0.44, 0.48) });
    }

    // ---------------------------------------------------- end cap
    if (outrunner && definition.includeEndCap)
    {
        // Closes the -Z end of the housing, so the +Z end stays open for the stator.
        const capBore = definition.endCapBore / 2;
        if (capBore >= coreOut)
            throw regenError("The end cap bore must be smaller than the rotor outer diameter.", ["endCapBore"]);
        const capId = id + "endCap";
        tfmRing(context, capId, capBore, coreOut, z0 - definition.endCapThickness, z0);
        setProperty(context, { "entities" : tfmSolids(capId), "propertyType" : PropertyType.NAME, "value" : "Rotor end cap" });
        setProperty(context, { "entities" : tfmSolids(capId), "propertyType" : PropertyType.APPEARANCE, "value" : color(0.42, 0.44, 0.48) });
    }

    // --------------------------------------- magnetisation arrows
    if (definition.showArrows && !axial)
    {
        // Drawn on the +Z end face of the first phase, for the magnets of its last row.
        const arrowSketch = newSketchOnPlane(context, id + "arrows", {
                    "sketchPlane" : plane(vector(zero, zero, z0 + stack), vector(0, 0, 1), vector(1, 0, 0))
                });
        const topShift = (alternate && (rows - 1) % 2 == 1) ? polePitch : 0;
        const rc = (ra + rb) / 2;
        const tangentialWidth = fluxConcentrating ? wm : span * rc;
        const arrowLength = 0.6 * (hm < tangentialWidth ? hm : tangentialWidth);
        var n = 0;
        for (var k = 0; k < size(electricalAngles); k += 1)
        {
            const beta = rotorMagnetAngle(electricalAngles[k], outrunner) * degree;
            const offset = electricalAngles[k] / 180 * polePitch;
            for (var j = 0; j < poles / 2; j += 1)
            {
                const theta = (offset + 2 * j * polePitch + topShift) * radian;
                const radial = vector(cos(theta), sin(theta));
                const tangent = vector(-sin(theta), cos(theta));
                const direction = radial * cos(beta) + tangent * sin(beta);
                const normal = vector(-direction[1], direction[0]);
                const tip = radial * rc + direction * (arrowLength / 2);
                const tail = radial * rc - direction * (arrowLength / 2);
                const barb = tip - direction * (0.3 * arrowLength);
                skLineSegment(arrowSketch, "shaft" ~ n, { "start" : tail, "end" : tip });
                skLineSegment(arrowSketch, "barbA" ~ n, { "start" : tip, "end" : barb + normal * (0.18 * arrowLength) });
                skLineSegment(arrowSketch, "barbB" ~ n, { "start" : tip, "end" : barb - normal * (0.18 * arrowLength) });
                n += 1;
            }
        }
        skSolve(arrowSketch);
    }
}

const TFM_ROTOR_DEFAULTS = {
            "configuration" : TfmRotorConfiguration.INRUNNER,
            "rotorType" : TfmRotorType.SURFACE,
            "outerDiameter" : 118 * millimeter,
            "shaftDiameter" : 30 * millimeter,
            "outrunnerInnerDiameter" : 122 * millimeter,
            "outrunnerOuterDiameter" : 160 * millimeter,
            "stackLength" : 40 * millimeter,
            "phases" : 1,
            "phaseSpacing" : 1 * millimeter,
            "poles" : 32,
            "magnetThickness" : 5 * millimeter,
            "magnetArcRatio" : 0.85,
            "segmentsPerPole" : 2,
            "fcMagnetHeight" : 12 * millimeter,
            "fcMagnetWidth" : 4 * millimeter,
            "magnetRows" : 1,
            "rowGap" : 20 * millimeter,
            "alternateRows" : true,
            "includeShaft" : false,
            "shaftExtension" : 20 * millimeter,
            "includeEndCap" : false,
            "endCapThickness" : 5 * millimeter,
            "endCapBore" : 10 * millimeter,
            "showArrows" : true
        };

// --------------------------------------------------------------- helpers

/**
 * Seed body for a magnet or a disc tooth, centred on the +X axis: an outline symmetric about X,
 * bounded by arcs of radius rIn and rOut around the Z axis, extruded from zMin by `depth` along +Z.
 * `inner` and `outer` are the corners of the outline on the +Y side, on the inner and the outer arc.
 */
function rotorSector(context is Context, id is Id, zMin is ValueWithUnits, depth is ValueWithUnits,
    rIn is ValueWithUnits, rOut is ValueWithUnits, inner is Vector, outer is Vector)
{
    const zero = 0 * meter;
    const sketch = newSketchOnPlane(context, id + "sketch", {
                "sketchPlane" : plane(vector(zero, zero, zMin), vector(0, 0, 1), vector(1, 0, 0))
            });
    skLineSegment(sketch, "side1", { "start" : vector(inner[0], -inner[1]), "end" : vector(outer[0], -outer[1]) });
    skArc(sketch, "outer", { "start" : vector(outer[0], -outer[1]), "mid" : vector(rOut, zero), "end" : outer });
    skLineSegment(sketch, "side2", { "start" : outer, "end" : inner });
    skArc(sketch, "inner", { "start" : inner, "mid" : vector(rIn, zero), "end" : vector(inner[0], -inner[1]) });
    skSolve(sketch);
    opExtrude(context, id + "extrude", {
                "entities" : qSketchRegion(id + "sketch"),
                "direction" : vector(0, 0, 1),
                "endBound" : BoundingType.BLIND,
                "endDepth" : depth
            });
    opDeleteBodies(context, id + "deleteSketch", { "entities" : qCreatedBy(id + "sketch", EntityType.BODY) });
}

/**
 * Magnetisation angle in degrees, measured from the local radial direction towards +theta, for a
 * magnet centred at the given electrical angle. The strong side of a Halbach array is the air gap:
 * outside for an inrunner, inside for an outrunner.
 */
function rotorMagnetAngle(electricalAngle is number, outrunner is boolean) returns number
{
    return outrunner ? (electricalAngle + 180) % 360 : (360 - electricalAngle) % 360;
}

/**
 * Part name for a magnet whose magnetisation is rotated `beta` degrees from the radial direction.
 * N and S name the pole that faces the air gap.
 */
function rotorMagnetName(beta is number, outrunner is boolean) returns string
{
    if (abs(beta) < 1e-6)
        return outrunner ? "Magnet S (radial out)" : "Magnet N (radial out)";
    if (abs(beta - 180) < 1e-6)
        return outrunner ? "Magnet N (radial in)" : "Magnet S (radial in)";
    const signed = beta > 180 ? beta - 360 : beta;
    return "Magnet (magnetised " ~ roundToPrecision(signed, 1) ~ " deg from radial)";
}

/** Colour by angle in degrees: 0 = red (north faces the gap), 90 = yellow, 180 = green (south), 270 = blue. */
function rotorMagnetColor(beta is number)
{
    const anchors = [[0.80, 0.15, 0.15], [0.92, 0.75, 0.15], [0.15, 0.60, 0.25], [0.15, 0.35, 0.80], [0.80, 0.15, 0.15]];
    const x = beta / 90;
    var i = floor(x);
    if (i > 3)
        i = 3;
    const f = x - i;
    const a = anchors[i];
    const b = anchors[i + 1];
    return color(a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2]));
}
