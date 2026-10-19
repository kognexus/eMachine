FeatureScript 3095;
import(path : "onshape/std/geometry.fs", version : "3095.0");

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

annotation { "Feature Type Name" : "TFM stator",
        "Feature Type Description" : "Transverse flux machine stator core structures (U, UI, toothed ring, C, claw-pole, E, Z) after Kaiser and Parspour, IEEE Access 2022, Fig. 4 and 17." }
export const tfmStator = defineFeature(function(context is Context, id is Id, definition is map)
    precondition
    {
        annotation { "Name" : "Core structure" }
        definition.coreType is TfmCoreType;

        annotation { "Name" : "Arrangement" }
        definition.arrangement is TfmArrangement;

        if (definition.arrangement == TfmArrangement.LINEAR)
        {
            annotation { "Name" : "Pole pitch" }
            isLength(definition.polePitch, TFM_10MM_BOUNDS);

            annotation { "Name" : "Pole pairs" }
            isInteger(definition.linearPolePairs, TFM_LINEAR_PAIRS_BOUNDS);
        }
        else
        {
            annotation { "Name" : "Air-gap radius" }
            isLength(definition.airGapRadius, TFM_60MM_BOUNDS);

            annotation { "Name" : "Pole pairs" }
            isInteger(definition.rotaryPolePairs, TFM_ROTARY_PAIRS_BOUNDS);

            annotation { "Name" : "Inner stator (outer rotor)" }
            definition.innerStator is boolean;

            annotation { "Name" : "Trim pole faces to air-gap cylinder", "Default" : true }
            definition.trimPoleFaces is boolean;

            annotation { "Name" : "Number of phases" }
            isInteger(definition.phases, TFM_PHASES_BOUNDS);

            // Always shown: Onshape's precondition analysis rejects numeric comparisons such as
            // phases > 1. The spacing is ignored for a single phase.
            annotation { "Name" : "Phase spacing" }
            isLength(definition.phaseSpacing, TFM_1MM_BOUNDS);

            annotation { "Name" : "Pole shift angle" }
            isAngle(definition.poleShift, TFM_POLE_SHIFT_BOUNDS);
        }

        annotation { "Name" : "Tooth span / pole pitch" }
        isReal(definition.toothSpan, TFM_TOOTH_SPAN_BOUNDS);

        annotation { "Name" : "Leg width" }
        isLength(definition.legWidth, TFM_10MM_BOUNDS);

        annotation { "Name" : "Slot width" }
        isLength(definition.slotWidth, TFM_20MM_BOUNDS);

        annotation { "Name" : "Slot height" }
        isLength(definition.slotHeight, TFM_25MM_BOUNDS);

        annotation { "Name" : "Yoke height" }
        isLength(definition.yokeHeight, TFM_10MM_BOUNDS);

        if (definition.coreType == TfmCoreType.UI_CORE)
        {
            annotation { "Name" : "I-bridge height" }
            isLength(definition.bridgeHeight, TFM_6MM_BOUNDS);

            annotation { "Name" : "I-bridge top width / slot width" }
            isReal(definition.bridgeTopRatio, TFM_BRIDGE_TOP_BOUNDS);
        }

        if (definition.coreType == TfmCoreType.TR_CORE)
        {
            annotation { "Name" : "Ring tooth height" }
            isLength(definition.ringToothHeight, TFM_8MM_BOUNDS);

            annotation { "Name" : "Arched valleys between teeth", "Default" : false }
            definition.archedValleys is boolean;

            annotation { "Name" : "Staggered teeth (back wall one pole pitch later)", "Default" : false }
            definition.staggeredTeeth is boolean;
        }

        if (definition.coreType == TfmCoreType.C_CORE || definition.coreType == TfmCoreType.E_CORE)
        {
            annotation { "Name" : "Yoke skew transition / slot width" }
            isReal(definition.skewFraction, TFM_SKEW_BOUNDS);
        }

        if (definition.coreType == TfmCoreType.CP_CORE)
        {
            annotation { "Name" : "Claw root height" }
            isLength(definition.clawRootHeight, TFM_8MM_BOUNDS);

            annotation { "Name" : "Claw tip height" }
            isLength(definition.clawTipHeight, TFM_2MM_BOUNDS);

            annotation { "Name" : "Claw tip gap" }
            isLength(definition.clawTipGap, TFM_1MM_BOUNDS);
        }

        if (definition.coreType == TfmCoreType.E_CORE)
        {
            annotation { "Name" : "Middle leg width" }
            isLength(definition.midLegWidth, TFM_20MM_BOUNDS);
        }

        if (definition.coreType == TfmCoreType.Z_CORE)
        {
            annotation { "Name" : "Tooth height" }
            isLength(definition.zToothHeight, TFM_12MM_BOUNDS);

            annotation { "Name" : "Tooth width" }
            isLength(definition.zToothWidth, TFM_10MM_BOUNDS);

            annotation { "Name" : "Tooth to leg gap" }
            isLength(definition.zSlotGap, TFM_2MM_BOUNDS);

            annotation { "Name" : "Rotor gap height" }
            isLength(definition.zRotorGap, TFM_6MM_BOUNDS);
        }

        annotation { "Name" : "Include coil", "Default" : true }
        definition.includeCoil is boolean;

        if (definition.includeCoil)
        {
            annotation { "Name" : "Coil height" }
            isLength(definition.coilHeight, TFM_12MM_BOUNDS);

            annotation { "Name" : "Coil clearance" }
            isLength(definition.coilClearance, TFM_1MM_BOUNDS);
        }
    }
    {
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
    }, {
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
        });

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
