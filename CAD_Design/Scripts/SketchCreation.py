"""
Fusion 360 Script: Body -> 6-Sided Sketches (on the body's own surfaces)
---------------------------------------------------------------------------
WHAT THIS DOES
Select a solid body (or a whole component/occurrence) in your CAD model
and run this script. It creates SIX new sketches -- Top, Bottom, Front,
Back, Left, and Right -- one per side of the body's bounding box, with
the body's silhouette projected onto each.
 
IMPORTANT -- "on the body itself": unlike a naive version that sketches
on the component's origin planes (which pass through 0,0,0 and usually
float away from the actual part), each of the 6 planes here is offset to
sit exactly at the body's real extent on that side -- e.g. the "Top"
plane sits at the body's actual highest Z point, so it is coincident with
the model's top surface (flush against it, not hovering above/below).
Same idea for all 6 sides, using the body's bounding box.
 
If, instead of a body, you also have a single PLANAR FACE selected when
you run the script, it additionally creates one more sketch directly on
that face's own plane (a 7th, exact view) -- useful for a face that isn't
axis-aligned, e.g. an angled mounting face.
 
HOW THE PROJECTION WORKS (verified against current Fusion API docs, and
tested against a live document before this script was finalized)
This uses `Sketch.project2(entities, isLinked)`. Per Autodesk's API
reference, passing a BRepBody to project2 "results in projecting the
silhouette of the body" -- i.e. the outline you'd see looking straight
along that plane's normal. This is the current, supported method (the
older `Sketch.project()` was retired by Autodesk in May 2025).
NOTE: project2 requires a plain Python list of entities, not an
adsk.core.ObjectCollection -- passing an ObjectCollection raises a
TypeError from the underlying SWIG binding (confirmed live).
 
isLinked is set to False below, so the created sketch curves are
independent copies, not parametrically tied to the source body -- edit
them freely without worrying about breaking the original model. Set
LINK_TO_MODEL = True at the top of the script if you'd rather have the
sketches auto-update whenever the body changes.
 
VIEW-DIRECTION CONVENTION (flip if your model is oriented differently)
  Top/Bottom  = max/min Z      Front/Back = min/max Y      Right/Left = max/min X
This matches Fusion's default camera-view naming, but if your model's
"front" actually faces a different axis in your file, just relabel the
LABELS dict below -- the planes themselves are still correct, only the
names would be swapped.
 
LIMITATIONS TO KNOW ABOUT
  - This gives you an outline (silhouette) on each face, not a full
    engineering drawing with hidden-line removal, dimensions, section
    views, or hatching. For that, use Fusion's "Create Drawing" feature
    instead, which produces a proper .dwg/.idw-style drawing document.
  - If the body isn't axis-aligned (rotated relative to the component's
    origin), the bounding-box planes will still touch the body's extreme
    points, but may not sit flush against an actual flat face. In that
    case, select the specific face you want instead (see the 7th-view
    behavior above) rather than relying on the 6 auto-generated ones.
  - For a body with a lot of internal/curved detail, the silhouette can
    look sparse (it's the outer boundary as seen from that direction, not
    every visible edge). Set INCLUDE_ALL_EDGES = True below to project
    every edge instead.
 
HOW TO RUN
  Fusion 360 > Utilities tab > Scripts and Add-ins > "+" > select this
  file > Run. Select your body (or a planar face on it) in the model
  first, or the script will prompt you to pick it.
"""
 
import adsk.core
import adsk.fusion
import traceback
 
# Set to True to have the created sketch curves stay parametrically linked
# to the source body (they'll update automatically if the body changes).
# False (default) creates independent, freely-editable sketch geometry.
LINK_TO_MODEL = False
 
# Set to True to project every edge of the body instead of just the
# silhouette outline. Silhouette (False) is cleaner for a simple profile;
# all-edges (True) shows internal detail (holes, fillets, etc.) too but
# can get visually busy.
INCLUDE_ALL_EDGES = False
 
 
def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design: adsk.fusion.Design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox('No active Fusion design. Open/activate a design first.')
            return
 
        target_bodies, target_face, source_label = _resolve_selection(app, ui)
        if not target_bodies:
            return  # user cancelled or nothing usable was selected
 
        component = target_bodies[0].parentComponent
 
        # Combined bounding box across all target bodies (handles the
        # multi-body-occurrence case; for a single body it's just that
        # body's own box).
        bbox = _combined_bounding_box(target_bodies)
 
        # Each entry: (base origin plane, offset distance, label). The
        # offset places the new plane exactly at the body's real extent
        # on that side, so the sketch plane is coincident with the
        # model's own surface rather than floating at the origin.
        view_specs = [
            (component.xYConstructionPlane, bbox.maxPoint.z, 'Top'),
            (component.xYConstructionPlane, bbox.minPoint.z, 'Bottom'),
            (component.xZConstructionPlane, bbox.minPoint.y, 'Front'),
            (component.xZConstructionPlane, bbox.maxPoint.y, 'Back'),
            (component.yZConstructionPlane, bbox.maxPoint.x, 'Right'),
            (component.yZConstructionPlane, bbox.minPoint.x, 'Left'),
        ]
 
        created_names = []
        for base_plane, offset, label in view_specs:
            plane = _offset_plane(component, base_plane, offset,
                                   f'{source_label} - {label} Plane')
            sketch = component.sketches.add(plane)
            sketch.name = f'{source_label} - {label} View'
            created_curves = sketch.project2(_entities_for(target_bodies), LINK_TO_MODEL)
            created_names.append(f'{sketch.name} ({len(created_curves)} curves)')
 
        if target_face is not None:
            sketch = component.sketches.add(target_face)
            sketch.name = f'{source_label} - Selected Face View'
            created_curves = sketch.project2(_entities_for(target_bodies), LINK_TO_MODEL)
            created_names.append(f'{sketch.name} ({len(created_curves)} curves)')
 
        ui.messageBox(
            f'Created {len(created_names)} sketch(es) from "{source_label}", '
            'each flush against that side of the model:\n\n'
            + '\n'.join(f'  - {n}' for n in created_names) +
            '\n\nFind them (and their matching construction planes) in the '
            'browser tree under the component\'s Sketches / Construction '
            'folders.'
        )
 
    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
 
 
def _combined_bounding_box(bodies):
    """Axis-aligned bounding box covering every body in the list."""
    box = bodies[0].boundingBox
    min_pt = [box.minPoint.x, box.minPoint.y, box.minPoint.z]
    max_pt = [box.maxPoint.x, box.maxPoint.y, box.maxPoint.z]
    for body in bodies[1:]:
        b = body.boundingBox
        min_pt = [min(min_pt[0], b.minPoint.x), min(min_pt[1], b.minPoint.y), min(min_pt[2], b.minPoint.z)]
        max_pt = [max(max_pt[0], b.maxPoint.x), max(max_pt[1], b.maxPoint.y), max(max_pt[2], b.maxPoint.z)]
 
    class _Box:
        pass
 
    result = _Box()
    result.minPoint = adsk.core.Point3D.create(*min_pt)
    result.maxPoint = adsk.core.Point3D.create(*max_pt)
    return result
 
 
def _offset_plane(component: adsk.fusion.Component, base_plane, offset: float, name: str):
    plane_input = component.constructionPlanes.createInput()
    plane_input.setByOffset(base_plane, adsk.core.ValueInput.createByReal(offset))
    plane = component.constructionPlanes.add(plane_input)
    plane.name = name
    return plane
 
 
def _entities_for(bodies):
    # project2 requires a plain list, not an ObjectCollection.
    entities = []
    if INCLUDE_ALL_EDGES:
        for body in bodies:
            for face in body.faces:
                entities.append(face)
    else:
        for body in bodies:
            entities.append(body)
    return entities
 
 
def _resolve_selection(app: adsk.core.Application, ui: adsk.core.UserInterface):
    """
    Figures out what to project from the current selection (or prompts
    the user if nothing usable is already selected).
 
    Returns (list_of_BRepBody, planar_face_or_None, label_for_naming).
    Returns ([], None, '') if the user cancels.
    """
    sel_input = None
 
    # Check what's already selected before prompting.
    selections = ui.activeSelections
    if selections.count == 1:
        entity = selections.item(0).entity
        if entity.objectType == adsk.fusion.BRepBody.classType():
            return [entity], None, entity.name
        if entity.objectType == adsk.fusion.BRepFace.classType():
            face: adsk.fusion.BRepFace = entity
            if face.geometry.surfaceType != adsk.core.SurfaceTypes.PlaneSurfaceType:
                ui.messageBox('The selected face is not planar, so it can\'t '
                               'be used as a sketch plane. Pick a flat face, '
                               'a body, or run again and let the script '
                               'prompt you.')
                return [], None, ''
            return [face.body], face, face.body.name
        if entity.objectType == adsk.fusion.Occurrence.classType():
            occ: adsk.fusion.Occurrence = entity
            bodies = [b for b in occ.bRepBodies]
            if bodies:
                return bodies, None, occ.name
 
    # Nothing usable pre-selected -- prompt interactively.
    try:
        sel_input = ui.selectEntity(
            'Select the body (or a planar face on it) to turn into sketches',
            'Bodies,Faces,Occurrences'
        )
    except RuntimeError:
        return [], None, ''  # user pressed Escape / cancelled
 
    entity = sel_input.entity
    if entity.objectType == adsk.fusion.BRepBody.classType():
        return [entity], None, entity.name
    if entity.objectType == adsk.fusion.BRepFace.classType():
        face: adsk.fusion.BRepFace = entity
        if face.geometry.surfaceType != adsk.core.SurfaceTypes.PlaneSurfaceType:
            ui.messageBox('That face is not planar, so it can\'t be used as '
                           'a sketch plane. Re-run and pick a flat face or '
                           'the whole body instead.')
            return [], None, ''
        return [face.body], face, face.body.name
    if entity.objectType == adsk.fusion.Occurrence.classType():
        occ: adsk.fusion.Occurrence = entity
        bodies = [b for b in occ.bRepBodies]
        if not bodies:
            ui.messageBox('That component/occurrence has no bodies in it.')
            return [], None, ''
        return bodies, None, occ.name
 
    ui.messageBox('Unsupported selection type. Pick a body, a planar face, '
                   'or a component/occurrence.')
    return [], None, ''