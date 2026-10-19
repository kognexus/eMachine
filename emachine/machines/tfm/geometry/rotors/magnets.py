"""Magnet naming and magnetisation angles, the same as the Onshape feature "TFM rotor"."""


def magnet_angle(electrical, outrunner):
    """Magnetisation angle in degrees from the local radial direction towards +theta."""
    return (electrical + 180.0) % 360.0 if outrunner else (360.0 - electrical) % 360.0


def magnet_name(beta, outrunner):
    """Same names as the Onshape feature. N and S name the pole that faces the air gap."""
    if abs(beta) < 1e-6:
        return "Magnet S (radial out)" if outrunner else "Magnet N (radial out)"
    if abs(beta - 180) < 1e-6:
        return "Magnet N (radial in)" if outrunner else "Magnet S (radial in)"
    signed = beta - 360 if beta > 180 else beta
    return "Magnet (magnetised {:g} deg from radial)".format(round(signed, 1))
