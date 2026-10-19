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
