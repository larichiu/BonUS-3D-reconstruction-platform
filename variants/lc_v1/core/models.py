from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PatientData:
    root: Path
    frames_dir: Path
    masks_dir: Path
    pose_file: Path
    poses: pd.DataFrame
    matches: pd.DataFrame
    frame_size: tuple[int, int]
    label_source: str = "Local mask folder"
    annotation_sequence_id: int | None = None


@dataclass(frozen=True)
class ReconstructionSettings:
    spacing_x_mm: float = 0.05392
    spacing_y_mm: float = 0.05392
    tip_offset_mm: tuple[float, float, float] = (-163.326, -19.6482, -206.473)
    sample_step_px: int = 2
    frame_step: int = 1
    mask_threshold: int = 127
    flip_horizontal: bool = True
    # User-specified image directions: negative local X and negative local Z.
    flip_depth: bool = True
    use_reference: bool = True
    orientation_deg: tuple[float, float, float] = (0., 0., 0.)

    rotation_u_deg: float = 0.0
    rotation_v_deg: float = 0.0

    @property
    def baseline_image_basis(self):
        x,y,z = np.deg2rad(self.orientation_deg)
        cx,sx,cy,sy,cz,sz = np.cos(x),np.sin(x),np.cos(y),np.sin(y),np.cos(z),np.sin(z)
        rx=np.array([[1,0,0],[0,cx,-sx],[0,sx,cx]])
        ry=np.array([[cy,0,sy],[0,1,0],[-sy,0,cy]])
        rz=np.array([[cz,-sz,0],[sz,cz,0],[0,0,1]])
        r=rz@ry@rx
        return r[:,0]*(-1 if self.flip_horizontal else 1), r[:,2]*(-1 if self.flip_depth else 1)

    @property
    def image_basis(self):
        # Extrinsic right-hand rotations about the baseline image axes:
        # first lateral u, then longitudinal/depth v. Pivot is the tip.
        u, v = self.baseline_image_basis
        def rotation(axis, degrees):
            angle = np.deg2rad(degrees)
            x, y, z = axis
            skew = np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])
            return np.eye(3) + np.sin(angle)*skew + (1-np.cos(angle))*(skew@skew)
        adjustment = rotation(v, self.rotation_v_deg) @ rotation(u, self.rotation_u_deg)
        return adjustment @ u, adjustment @ v

    def image_points(self, u, v):
        right,depth=self.image_basis
        return (np.asarray(u)[:,None]*self.spacing_x_mm*right +
                np.asarray(v)[:,None]*self.spacing_y_mm*depth + self.tip_offset)

    @property
    def tip_offset(self) -> np.ndarray:
        return np.asarray(self.tip_offset_mm, dtype=np.float64)
