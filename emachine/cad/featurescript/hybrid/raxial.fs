FeatureScript 3095;
import(path : "onshape/std/geometry.fs", version : "3095.0");

/**
 * Raxial machine: the radial-axial flux PM machine with a toroidal winding (hybrid machines, T53, T54),
 * as the ARF-PMSM of Zhang, Liu, Wu, Electronics 2023, 12, 2867.
 *
 * An SMC stator: a ring yoke whose teeth stand out radially (towards an outer rotor ring with radial
 * magnets) and axially on both end faces (towards two rotor discs with axial magnets); inner teeth
 * carry the stator on its support. One toroidal coil around the yoke in every slot, coloured by
 * phase (slot star, machines/winding_layout.py toroidal). The machine axis is the world Z axis, the
 * stack is centred on Z = 0.
 *
 * The dialog takes the inputs of a specification and the design variables of rafm/pmsm
 * (docs/parameters.md); the other dimensions are derived as machines/rafm/dimensions.py does, and
 * inputs that leave no room stop with a message naming the fields. "python -m emachine onshape
 * --spec ... --design ..." prints the values of a design. Defaults: the paper's machine
 * (specs/rafm_zhang2023*.json).
 */

const RX_1MM = { (meter) : [0, 0.001, 500], (centimeter) : 0.1, (millimeter) : 1.0, (inch) : 0.04 } as LengthBoundSpec;
const RX_10MM = { (meter) : [0, 0.010, 500], (centimeter) : 1.0, (millimeter) : 10.0, (inch) : 0.4 } as LengthBoundSpec;
const RX_100MM = { (meter) : [1e-4, 0.100, 500], (centimeter) : 10.0, (millimeter) : 100.0, (inch) : 4.0 } as LengthBoundSpec;
const RX_PHASES = { (unitless) : [1, 3, 6] } as IntegerBoundSpec;
const RX_POLE_PAIRS = { (unitless) : [1, 10, 500] } as IntegerBoundSpec;
const RX_SLOTS = { (unitless) : [3, 24, 500] } as IntegerBoundSpec;
const RX_ARC = { (degree) : [0, 150, 180], (radian) : 2.618 } as AngleBoundSpec;

const RX_DEFAULTS = {
        "outerDiameter" : 400 * millimeter, "axialLength" : 112 * millimeter, "airGap" : 1 * millimeter,
        "boreDiameter" : 200 * millimeter, "phases" : 3, "slots" : 24, "polePairs" : 10,
        "rotorIron" : 19 * millimeter, "magnetThickness" : 5 * millimeter, "magnetArc" : 147.6 * degree,
        "radialToothHeight" : 25 * millimeter, "radialToothLength" : 28 * millimeter, "yokeWidth" : 30 * millimeter,
        "axialToothHeight" : 20 * millimeter, "discIron" : 10 * millimeter, "axialMagnetThickness" : 5 * millimeter,
        "axialMagnetArc" : 135.54 * degree, "slotWidth" : 16 * millimeter, "slotOpening" : 4 * millimeter,
        "toothTipHeight" : 2 * millimeter, "coilThickness" : 17 * millimeter, "coilClearance" : 0.5 * millimeter,
        "includeStator" : true, "includeCoil" : true, "includeRotor" : true
    };

annotation { "Feature Type Name" : "Raxial machine",
        "Feature Type Description" : "Hybrid machine: radial-axial flux PMSM with a toroidal winding (outer rotor ring and two rotor discs), from the inputs and design variables of rafm/pmsm." }
export const raxialMachine = defineFeature(function(context is Context, id is Id, definition is map)
    precondition
    {
        annotation { "Name" : "Outer diameter (radial rotor)" }
        isLength(definition.outerDiameter, RX_100MM);

        annotation { "Name" : "Total axial length" }
        isLength(definition.axialLength, RX_100MM);

        annotation { "Name" : "Air gap (radial and axial)" }
        isLength(definition.airGap, RX_1MM);

        annotation { "Name" : "Bore diameter (stator support)" }
        isLength(definition.boreDiameter, RX_100MM);

        annotation { "Name" : "Number of phases" }
        isInteger(definition.phases, RX_PHASES);

        annotation { "Name" : "Slots" }
        isInteger(definition.slots, RX_SLOTS);

        annotation { "Name" : "Pole pairs" }
        isInteger(definition.polePairs, RX_POLE_PAIRS);

        annotation { "Name" : "Radial rotor iron" }
        isLength(definition.rotorIron, RX_10MM);

        annotation { "Name" : "Radial magnet thickness" }
        isLength(definition.magnetThickness, RX_1MM);

        annotation { "Name" : "Radial magnet arc (electrical, 180: whole pole)" }
        isAngle(definition.magnetArc, RX_ARC);

        annotation { "Name" : "Radial tooth height" }
        isLength(definition.radialToothHeight, RX_10MM);

        annotation { "Name" : "Radial tooth axial length" }
        isLength(definition.radialToothLength, RX_10MM);

        annotation { "Name" : "Yoke width (radial)" }
        isLength(definition.yokeWidth, RX_10MM);

        annotation { "Name" : "Axial tooth height" }
        isLength(definition.axialToothHeight, RX_10MM);

        annotation { "Name" : "Disc iron" }
        isLength(definition.discIron, RX_10MM);

        annotation { "Name" : "Axial magnet thickness" }
        isLength(definition.axialMagnetThickness, RX_1MM);

        annotation { "Name" : "Axial magnet arc (electrical, 180: whole pole)" }
        isAngle(definition.axialMagnetArc, RX_ARC);

        annotation { "Name" : "Slot width (parallel-sided)" }
        isLength(definition.slotWidth, RX_10MM);

        annotation { "Name" : "Slot opening" }
        isLength(definition.slotOpening, RX_1MM);

        annotation { "Name" : "Tooth tip height" }
        isLength(definition.toothTipHeight, RX_1MM);

        annotation { "Name" : "Coil thickness (around the yoke)" }
        isLength(definition.coilThickness, RX_10MM);

        annotation { "Name" : "Coil clearance" }
        isLength(definition.coilClearance, RX_1MM);

        annotation { "Name" : "Include stator", "Default" : true }
        definition.includeStator is boolean;

        annotation { "Name" : "Include coils", "Default" : true }
        definition.includeCoil is boolean;

        annotation { "Name" : "Include rotor", "Default" : true }
        definition.includeRotor is boolean;
    }
    {
        const g = rxDimensions(definition);
        if (definition.includeStator)
            rxStator(context, id + "stator", definition, g);
        if (definition.includeCoil)
            rxCoils(context, id + "coil", definition, g);
        if (definition.includeRotor)
            rxRotor(context, id + "rotor", definition, g);
    }, RX_DEFAULTS);

const RX_PHASE_COLORS = [color(0.85, 0.45, 0.18), color(0.20, 0.45, 0.80), color(0.25, 0.60, 0.30),
        color(0.60, 0.30, 0.70), color(0.85, 0.75, 0.20), color(0.40, 0.40, 0.40)];
const RX_PHASE_NAMES = ["A", "B", "C", "D", "E", "F"];
const EM_STEEL = color(0.62, 0.62, 0.64);
const EM_ROTOR_STEEL = color(0.42, 0.43, 0.46);
const EM_NORTH = color(0.80, 0.15, 0.15);
const EM_SOUTH = color(0.15, 0.60, 0.25);

/** Dimensions from the inputs, as machines/rafm/dimensions.py; stops when they leave no room. */
function rxDimensions(d is map) returns map
{
    const R = d.outerDiameter / 2;
    const L = d.axialLength;
    const a = d.coilClearance;
    const magnetIn = R - d.rotorIron - d.magnetThickness;      // inner radius of the radial magnets
    const Rs = magnetIn - d.airGap;                             // stator radius at the radial teeth
    const ryo = Rs - d.radialToothHeight;
    const ryi = ryo - d.yokeWidth;
    const Lc = L - 2 * (d.airGap + d.axialMagnetThickness + d.discIron);     // stator core length
    const hy = Lc - 2 * d.axialToothHeight;                     // yoke axial length
    const t = d.toothTipHeight;
    const c = d.coilThickness;
    const rb = d.boreDiameter / 2;
    const pitch = 2 * PI / d.slots;
    if (Lc <= 0 * meter || hy <= 0 * meter)
        throw regenError("No room for the stator core along the axis: reduce the axial tooth height, the disc iron or the axial magnets.", ["axialToothHeight", "discIron", "axialMagnetThickness", "axialLength"]);
    if (d.radialToothLength > Lc)
        throw regenError("The radial teeth are longer than the stator core.", ["radialToothLength"]);
    if (ryi <= rb)
        throw regenError("The yoke reaches into the bore.", ["yokeWidth", "radialToothHeight", "boreDiameter"]);
    if (c + a > Rs - t - ryo)
        throw regenError("The coil does not fit under the tips of the radial teeth.", ["coilThickness", "radialToothHeight"]);
    if (c + a > d.axialToothHeight - t)
        throw regenError("The coil does not fit under the tips of the axial teeth.", ["coilThickness", "axialToothHeight"]);
    if (c + a > ryi - rb)
        throw regenError("No room for the inner side of the coils between the bore and the yoke.", ["coilThickness", "boreDiameter"]);
    if (pitch * ryi <= d.slotWidth)
        throw regenError("No axial tooth is left at the inner edge of the yoke: reduce the slot width.", ["slotWidth", "slots"]);
    if (d.slotOpening >= d.slotWidth)
        throw regenError("The slot opening must be smaller than the slot width.", ["slotOpening"]);
    return { "R" : R, "L" : L, "magnetIn" : magnetIn, "Rs" : Rs, "ryo" : ryo, "ryi" : ryi, "Lc" : Lc, "hy" : hy,
            "rb" : rb, "c" : c, "a" : a };
}

/** Phase (0 based) and sign of the toroidal coil in each slot: the slot star in 360 / (2 m) belts. */
function rxPhases(slots is number, p is number, m is number) returns array
{
    const belt = 360 / (2 * m);
    var out = [];
    for (var k = 0; k < slots; k += 1)
    {
        const angle = rxMod(p * k * 360 / slots, 360);
        const index = floor(rxMod(angle + belt / 2, 360) / belt);
        const sign = index % 2 == 0 ? 1 : -1;
        const lag = rxMod(index * belt - (sign > 0 ? 0 : 180), 360);
        out = append(out, { "phase" : round(lag / (360 / m)) % m, "sign" : sign });
    }
    return out;
}

function rxMod(x is number, n is number) returns number
{
    return ((x % n) + n) % n;
}

/** Box x0..x1 (radial), y0..y1 (tangential), z0..z1 in the frame of a slot, turned to angleDeg about Z. */
function rxBox(context is Context, id is Id, x0, x1, y0, y1, z0, z1, angleDeg is number)
{
    fCuboid(context, id, { "corner1" : vector(x0, y0, z0), "corner2" : vector(x1, y1, z1) });
    if (abs(angleDeg) > 1e-12)
        opTransform(context, id + "turn", {
                    "bodies" : qCreatedBy(id, EntityType.BODY),
                    "transform" : rotationAround(line(vector(0, 0, 0) * meter, vector(0, 0, 1)), angleDeg * degree)
                });
}

/**
 * The SMC stator: the envelope (r_b..r_yo over the core length, and the radial teeth r_yo..R_s over
 * their axial length) less the slots. A slot is parallel-sided (width w) around the yoke section and
 * narrows to the opening at the tips of the radial and the axial teeth.
 */
function rxStator(context is Context, id is Id, d is map, g is map)
{
    const half = g.Lc / 2;
    emAnnulus(context, id + "body", g.rb, g.ryo, -half, g.Lc);
    emAnnulus(context, id + "teeth", g.ryo - 0.01 * millimeter, g.Rs, -d.radialToothLength / 2, d.radialToothLength);
    opBoolean(context, id + "join", {
                "tools" : qUnion([emSolids(id + "body"), emSolids(id + "teeth")]),
                "operationType" : BooleanOperationType.UNION
            });
    const w = d.slotWidth / 2;
    const b = d.slotOpening / 2;
    const t = d.toothTipHeight;
    const e = 1 * millimeter;
    const lr = d.radialToothLength / 2 + e;
    for (var k = 0; k < d.slots; k += 1)
    {
        const angle = k * 360 / d.slots;
        const s = id + "slots" + ("s" ~ k);
        rxBox(context, s + "inner", g.rb - e, g.ryi, -w, w, -half - e, half + e, angle);       // between the inner teeth
        rxBox(context, s + "radial", g.ryo, g.Rs - t, -w, w, -lr, lr, angle);                  // between the radial teeth
        rxBox(context, s + "radialTip", g.Rs - t - 0.01 * millimeter, g.Rs + e, -b, b, -lr, lr, angle);
        for (var side = -1; side <= 1; side += 2)
        {
            const zs = side > 0 ? "p" : "n";
            const z0 = g.hy / 2;
            const z1 = half - t;
            rxBox(context, s + ("axial" ~ zs), g.ryi, g.ryo, -w, w, side > 0 ? z0 : -z1, side > 0 ? z1 : -z0, angle);
            rxBox(context, s + ("axialTip" ~ zs), g.ryi, g.ryo, -b, b,
                    side > 0 ? z1 - 0.01 * millimeter : -half - e, side > 0 ? half + e : -z1 + 0.01 * millimeter, angle);
        }
    }
    opBoolean(context, id + "cutSlots", {
                "tools" : emSolids(id + "slots"),
                "targets" : qUnion([emSolids(id + "body"), emSolids(id + "teeth"), emSolids(id + "join")]),
                "operationType" : BooleanOperationType.SUBTRACTION
            });
    emStyle(context, emSolids(id), "Stator core (SMC)", EM_STEEL);        // the slot cutters are used up
}

/** One toroidal coil around the yoke section in every slot (four sides, clearance a, thickness c). */
function rxCoils(context is Context, id is Id, d is map, g is map)
{
    const phases = rxPhases(d.slots, d.polePairs, d.phases);
    const x0 = g.ryi - g.a - g.c;
    const x1 = g.ryo + g.a + g.c;
    const z1 = g.hy / 2 + g.a + g.c;
    const w = d.slotWidth / 2 - g.a;
    for (var k = 0; k < d.slots; k += 1)
    {
        const angle = k * 360 / d.slots;
        const coilId = id + ("c" ~ k);
        rxBox(context, coilId + "inner", x0, x0 + g.c, -w, w, -z1, z1, angle);
        rxBox(context, coilId + "outer", x1 - g.c, x1, -w, w, -z1, z1, angle);
        rxBox(context, coilId + "endP", x0, x1, -w, w, z1 - g.c, z1, angle);
        rxBox(context, coilId + "endN", x0, x1, -w, w, -z1, -z1 + g.c, angle);
        opBoolean(context, coilId + "join", {
                    "tools" : emSolids(coilId),
                    "operationType" : BooleanOperationType.UNION
                });
        const ph = phases[k];
        emStyle(context, emSolids(coilId), "Coil " ~ (k + 1) ~ " " ~ RX_PHASE_NAMES[ph.phase % 6] ~ (ph.sign > 0 ? "+" : "-"),
                RX_PHASE_COLORS[ph.phase % 6]);
    }
}

/**
 * The rotor: a ring of rotor iron over the whole length with the radial magnets inside it, and two
 * discs with the axial magnets facing the end faces of the stator. The three magnets of a pole are
 * at the same angle and show the same pole to the stator (magnet j centred at j * 180 / p; N for even j).
 */
function rxRotor(context is Context, id is Id, d is map, g is map)
{
    const half = g.L / 2;
    emAnnulus(context, id + "ring", g.R - d.rotorIron, g.R, -half, g.L);
    const z0 = g.Lc / 2 + d.airGap + d.axialMagnetThickness;            // inner face of a disc
    const discIn = g.ryi - 5 * millimeter;
    emAnnulus(context, id + "discP", discIn, g.R - d.rotorIron + 0.01 * millimeter, z0, d.discIron);
    emAnnulus(context, id + "discN", discIn, g.R - d.rotorIron + 0.01 * millimeter, -z0 - d.discIron, d.discIron);
    opBoolean(context, id + "join", {
                "tools" : qUnion([emSolids(id + "ring"), emSolids(id + "discP"), emSolids(id + "discN")]),
                "operationType" : BooleanOperationType.UNION
            });
    emStyle(context, qUnion([emSolids(id + "ring"), emSolids(id + "discP"), emSolids(id + "discN"), emSolids(id + "join")]),
            "Rotor (ring and discs)", EM_ROTOR_STEEL);
    const p = d.polePairs;
    const radialSpan = d.magnetArc / degree / p;
    const axialSpan = d.axialMagnetArc / degree / p;
    const za = g.Lc / 2 + d.airGap;
    for (var j = 0; j < 2 * p; j += 1)
    {
        const centre = j * 180 / p;
        const north = j % 2 == 0;
        const radialId = id + "magnets" + ("r" ~ j);
        emProfile(context, radialId, -d.radialToothLength / 2, d.radialToothLength,
                emRingSector(g.magnetIn, g.magnetIn + d.magnetThickness, centre - radialSpan / 2, centre + radialSpan / 2));
        rxMagnetStyle(context, radialId, north, "radial");
        const plusId = id + "magnets" + ("p" ~ j);
        emProfile(context, plusId, za, d.axialMagnetThickness,
                emRingSector(g.ryi, g.ryo, centre - axialSpan / 2, centre + axialSpan / 2));
        rxMagnetStyle(context, plusId, north, "axial, +Z disc");
        const minusId = id + "magnets" + ("n" ~ j);
        emProfile(context, minusId, -za - d.axialMagnetThickness, d.axialMagnetThickness,
                emRingSector(g.ryi, g.ryo, centre - axialSpan / 2, centre + axialSpan / 2));
        rxMagnetStyle(context, minusId, north, "axial, -Z disc");
    }
}

function rxMagnetStyle(context is Context, id is Id, north is boolean, where is string)
{
    emStyle(context, qCreatedBy(id, EntityType.BODY), "Magnet " ~ (north ? "N" : "S") ~ " to the stator (" ~ where ~ ")",
            north ? EM_NORTH : EM_SOUTH);
}
