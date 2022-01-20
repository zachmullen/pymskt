import vtk
import numpy as np
from vtk.util.numpy_support import vtk_to_numpy
from pymskt.utils import sigma2fwhm
# Some functions were originally based on the tutorial on ray casting in python + vtk 
# by Adamos Kyriakou @:
# https://pyscience.wordpress.com/2014/09/21/ray-casting-with-python-and-vtk-intersecting-linesrays-with-surface-meshes/
#
#

def is_hit(obb_tree, source, target):
    """
    Return True if line intersects mesh (`obb_tree`). The line starts at `source` and ends at `target`.

    Parameters
    ----------
    obb_tree : vtk.vtkOBBTree
        OBBTree of a surface mesh. 
    source : list
        x/y/z position of starting point of ray (to find intersection)
    target : list
        x/y/z position of ending point of ray (to find intersection)

    Returns
    -------
    bool
        Telling if the line (source to target) intersects the obb_tree. 
    """    

    code = obb_tree.IntersectWithLine(source, target, None, None)
    if code == 0:
        return False
    else: 
        return True


def get_intersect(obbTree, pSource, pTarget):
    """
    Get intersecting points on the obbTree between a line from pSource to pTarget. 

    Parameters
    ----------
    obb_tree : vtk.vtkOBBTree
        OBBTree of a surface mesh. 
    pSource : list
        x/y/z position of starting point of ray (to find intersection)
    pTarget : list
        x/y/z position of ending point of ray (to find intersection)

    Returns
    -------
    tuple (list1, list2)
        list1 is of the intersection points
        list2 is the idx of the cells that were intersected. 
    """    
    # Create an empty 'vtkPoints' object to store the intersection point coordinates
    points = vtk.vtkPoints()
    # Create an empty 'vtkIdList' object to store the ids of the cells that intersect
    # with the cast rays
    cell_ids = vtk.vtkIdList()

    # Perform intersection
    code = obbTree.IntersectWithLine(pSource, pTarget, points, cell_ids)

    # Get point-data
    point_data = points.GetData()
    # Get number of intersection points found
    n_points = point_data.GetNumberOfTuples()
    # Get number of intersected cell ids
    n_Ids = cell_ids.GetNumberOfIds()

    assert (n_points == n_Ids)

    # Loop through the found points and cells and store
    # them in lists
    points_inter = []
    cell_ids_inter = []
    for idx in range(n_points):
        points_inter.append(point_data.GetTuple3(idx))
        cell_ids_inter.append(cell_ids.GetId(idx))

    return points_inter, cell_ids_inter


def get_surface_normals(surface,
                        point_normals_on=True,
                        cell_normals_on=True):
    """
    Get the surface normals of a mesh (`surface`

    Parameters
    ----------
    surface : vtk.vtkPolyData
        surface mesh to get normals from 
    point_normals_on : bool, optional
        Whether or not to get normals of points (vertices), by default True
    cell_normals_on : bool, optional
        Whether or not to get normals from cells (faces?), by default True

    Returns
    -------
    vtk.vtkPolyDataNormals
        Normval vectors for points/cells. 
    """    

    normals = vtk.vtkPolyDataNormals()
    normals.SetInputData(surface)

    # Disable normal calculation at cell vertices
    if point_normals_on is True:
        normals.ComputePointNormalsOn()
    elif point_normals_on is False:
        normals.ComputePointNormalsOff()
    # Enable normal calculation at cell centers
    if cell_normals_on is True:
        normals.ComputeCellNormalsOn()
    elif cell_normals_on is False:
        normals.ComputeCellNormalsOff()
    # Disable splitting of sharp edges
    normals.SplittingOff()
    # Disable global flipping of normal orientation
    normals.FlipNormalsOff()
    # Enable automatic determination of correct normal orientation
    normals.AutoOrientNormalsOn()
    # Perform calculation
    normals.Update()

    return normals


def get_obb_surface(surface):
    """
    Get vtk.vtkOBBTree for a surface mesh
    Get obb of a surface mesh. This can be queried to see if a line etc. intersects a surface.

    Parameters
    ----------
    surface : vtk.vtkPolyData
        The surface mesh to get an OBBTree for. 

    Returns
    -------
    vtk.vtkOBBTree
        The OBBTree to be used to find intersections for calculating cartilage thickness etc. 
    """    

    obb = vtk.vtkOBBTree()
    obb.SetDataSet(surface)
    obb.BuildLocator()
    return obb


def vtk_deep_copy(mesh):
    """
    "Deep" copy a vtk.vtkPolyData so that they are not connected in any way. 

    Parameters
    ----------
    mesh : vtk.vtkPolyData
        Mesh to copy. 

    Returns
    -------
    vtk.vtkPolyData
        Copy of the input mesh. 
    """    
    new_mesh = vtk.vtkPolyData()
    new_mesh.DeepCopy(mesh)
    return new_mesh

def estimate_mesh_scalars_FWHMs(mesh, scalar_name='thickness_mm'):
    """
    Calculate the Full Width Half Maximum (FWHM) based on surface mesh scalars. 

    Parameters
    ----------
    mesh : vtk.vtkPolyData
        Surface mesh to estimate FWHM of the scalars from. 
    scalar_name : str, optional
        Name of the scalars to calcualte FWHM for, by default 'thickness_mm'

    Returns
    -------
    list
        List of the FWHM values. Assuming they are for X/Y/Z
    """    
    gradient_filter = vtk.vtkGradientFilter()
    gradient_filter.SetInputData(mesh)
    gradient_filter.Update()
    gradient_mesh = vtk.vtkPolyData()
    gradient_mesh.DeepCopy(gradient_filter.GetOutput())

    scalars = vtk_to_numpy(mesh.GetPointData().GetScalars())
    location_non_zero = np.where(scalars != 0)
    gradient_scalars = vtk_to_numpy(gradient_mesh.GetPointData().GetAbstractArray('Gradients'))
    cartilage_gradients = gradient_scalars[location_non_zero, :][0]

    thickness_scalars = vtk_to_numpy(gradient_mesh.GetPointData().GetAbstractArray(scalar_name))
    cartilage_thicknesses = thickness_scalars[location_non_zero]

    V0 = np.mean((cartilage_thicknesses - np.mean(cartilage_thicknesses)) ** 2)
    V1 = np.mean((cartilage_gradients - np.mean(cartilage_gradients)) ** 2, axis=0)
    sigma2s = -1 / (4 * np.log(1 - (V1 / (2 * V0))))
    sigmas = np.sqrt(sigma2s)
    FWHMs = [sigma2fwhm(x) for x in sigmas]

    return FWHMs