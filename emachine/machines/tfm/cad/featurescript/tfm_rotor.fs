FeatureScript 3095;
import(path : "onshape/std/geometry.fs", version : "3095.0");

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

annotation { "Feature Type Name" : "TFM rotor",
        "Feature Type Description" : "Permanent-magnet rotor, inrunner or outrunner, with one or more phases along the axis: interleaved N-S surface magnets, Halbach array, flux-concentrating spoke magnets, or an axially magnetised ring between toothed discs." }
export const tfmInrunnerRotor = defineFeature(function(context is Context, id is Id, definition is map)
    precondition
    {
        annotation { "Name" : "Configuration" }
        definition.configuration is TfmRotorConfiguration;

        annotation { "Name" : "Rotor type" }
        definition.rotorType is TfmRotorType;

        if (definition.configuration == TfmRotorConfiguration.INRUNNER)
        {
            annotation { "Name" : "Outer diameter (air gap)" }
            isLength(definition.outerDiameter, ROTOR_OD_BOUNDS);

            annotation { "Name" : "Shaft diameter" }
            isLength(definition.shaftDiameter, ROTOR_SHAFT_BOUNDS);
        }
        else
        {
            annotation { "Name" : "Inner diameter (air gap)" }
            isLength(definition.outrunnerInnerDiameter, ROTOR_OUT_ID_BOUNDS);

            annotation { "Name" : "Outer diameter" }
            isLength(definition.outrunnerOuterDiameter, ROTOR_OUT_OD_BOUNDS);
        }

        annotation { "Name" : "Stack length" }
        isLength(definition.stackLength, ROTOR_STACK_BOUNDS);

        annotation { "Name" : "Number of phases" }
        isInteger(definition.phases, ROTOR_PHASES_BOUNDS);

        // Always shown: Onshape's precondition analysis rejects numeric comparisons such as
        // phases > 1. The spacing is ignored for a single phase.
        annotation { "Name" : "Phase spacing" }
        isLength(definition.phaseSpacing, ROTOR_PHASE_SPACING_BOUNDS);

        annotation { "Name" : "Number of poles" }
        isInteger(definition.poles, ROTOR_POLES_BOUNDS);

        if (definition.rotorType == TfmRotorType.FLUX_CONCENTRATING)
        {
            annotation { "Name" : "Magnet radial height" }
            isLength(definition.fcMagnetHeight, ROTOR_FC_HEIGHT_BOUNDS);

            annotation { "Name" : "Magnet width" }
            isLength(definition.fcMagnetWidth, ROTOR_FC_WIDTH_BOUNDS);
        }
        else
        {
            // Axially magnetised type: radial height of the disc teeth.
            annotation { "Name" : "Magnet thickness" }
            isLength(definition.magnetThickness, ROTOR_MAGNET_BOUNDS);
        }

        if (definition.rotorType == TfmRotorType.SURFACE || definition.rotorType == TfmRotorType.AXIAL)
        {
            // Axially magnetised type: tooth arc / pole pitch.
            annotation { "Name" : "Magnet arc / pole pitch" }
            isReal(definition.magnetArcRatio, ROTOR_ARC_BOUNDS);
        }

        if (definition.rotorType == TfmRotorType.HALBACH)
        {
            annotation { "Name" : "Segments per pole" }
            isInteger(definition.segmentsPerPole, ROTOR_SEGMENTS_BOUNDS);
        }

        if (definition.rotorType != TfmRotorType.AXIAL)
        {
            annotation { "Name" : "Axial magnet rows" }
            isInteger(definition.magnetRows, ROTOR_ROWS_BOUNDS);
        }

        // Axially magnetised type: axial length of the ring magnet between the two discs.
        annotation { "Name" : "Gap between rows" }
        isLength(definition.rowGap, ROTOR_ROW_GAP_BOUNDS);

        if (definition.rotorType != TfmRotorType.AXIAL)
        {
            annotation { "Name" : "Alternate polarity between rows", "Default" : true }
            definition.alternateRows is boolean;
        }

        if (definition.configuration == TfmRotorConfiguration.INRUNNER)
        {
            annotation { "Name" : "Include shaft" }
            definition.includeShaft is boolean;

            if (definition.includeShaft)
            {
                annotation { "Name" : "Shaft extension per side" }
                isLength(definition.shaftExtension, ROTOR_SHAFT_EXT_BOUNDS);
            }
        }
        else
        {
            annotation { "Name" : "Include end cap" }
            definition.includeEndCap is boolean;

            if (definition.includeEndCap)
            {
                annotation { "Name" : "End cap thickness" }
                isLength(definition.endCapThickness, ROTOR_MAGNET_BOUNDS);

                annotation { "Name" : "End cap bore diameter" }
                isLength(definition.endCapBore, ROTOR_CAP_BORE_BOUNDS);
            }
        }

        if (definition.rotorType != TfmRotorType.AXIAL)
        {
            annotation { "Name" : "Show magnetization arrows", "Default" : true }
            definition.showArrows is boolean;
        }
    }
    {
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
    }, {
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
        });

// --------------------------------------------------------------- helpers

/** Solid bodies created by any operation below `id`. */
function tfmSolids(id is Id) returns Query
{
    return qBodyType(qCreatedBy(id, EntityType.BODY), BodyType.SOLID);
}

/** Ring around the world Z axis: radius from rMin to rMax, axial extent from zMin to zMax. */
function tfmRing(context is Context, id is Id, rMin is ValueWithUnits, rMax is ValueWithUnits,
    zMin is ValueWithUnits, zMax is ValueWithUnits)
{
    // Sketch plane through the rotor axis: sketch (u, v) maps to world (u, 0, v).
    const sketchPlane = plane(vector(0, 0, 0) * meter, vector(0, -1, 0), vector(1, 0, 0));
    const sketch = newSketchOnPlane(context, id + "sketch", { "sketchPlane" : sketchPlane });
    skRectangle(sketch, "section", {
                "firstCorner" : vector(rMin, zMin),
                "secondCorner" : vector(rMax, zMax)
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
