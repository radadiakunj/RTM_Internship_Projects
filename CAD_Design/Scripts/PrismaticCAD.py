"""
Fusion 360 Script: Select-and-Convert-Mesh Helper
----------------------------------------------------
WHAT THIS IS FOR
The parallel-line "striping" and triangulated look on curved regions of
your model (rounded corners, cylindrical bosses, etc.) is the mesh
faceting from the earlier Convert to Mesh step -- each thin strip is one
flat triangular facet standing in for what used to be a smooth curved
surface. This script gets you to the tool that fixes that.
 
WHAT THIS DOES
Select the body and run this script. It selects it for you and opens
Fusion's native "Convert Mesh" command (Design workspace > Mesh tab >
Modify > Convert), which is the tool that turns faceted mesh geometry
back into real, smooth, mathematically-defined surfaces.
 
THE ONE SETTING THAT MATTERS -- set this yourself in the dialog
Convert Mesh has a "Method" dropdown with two options:
  - "Faceted"   -- keeps the exact triangulated shape, just repackaged as
                   a BRep body. This does NOT remove the striping/facet
                   look -- it's the wrong option for what you want.
  - "Prismatic" -- analyzes the mesh and automatically groups faces into
                   flat (planar) and curved (cylindrical) regions, then
                   fits a single smooth mathematical surface to each
                   group. THIS is what eliminates the parallel-line
                   striping and gives you well-defined CAD geometry
                   again -- the rounded corner becomes one real
                   cylindrical fillet surface instead of ~20 flat strips.
 
Fusion's own tooltip for Convert Mesh confirms this: "Face groups are
used to infer prismatic features" -- i.e. Prismatic mode is the
auto-detection mode, not a fully manual one. You still get to review/
adjust the detected face groups before committing, which is your chance
to confirm it picked up the fillet and mounting boss correctly.
 
WHY THE SCRIPT CAN'T JUST FINISH THE JOB FOR YOU
Two hard limits, both confirmed by testing this live:
  1. No supported API sets the Method dropdown or commits the command
     for you -- Convert Mesh (like Reduce/Remesh/Repair before it) is a
     Mesh-tab command with no documented scripting surface. The only
     unofficial way in is `Commands.Start ParaMeshConvertCommand` via
     executeTextCommand, and even that only gets you to the same
     interactive dialog -- it can't fill in the Method or face groups
     for you either.
  2. Once that dialog is open, Fusion blocks ALL further scripting
     (including this add-in) until it's closed -- there is no way to
     drive the rest of the command from outside once it's up. This is a
     hard Fusion restriction, not a gap in this script.
  So: this script automates the "find and select the body, open the
  right tool" part (no manual hunting through menus), and you make the
  one Method choice and review the auto-detected face groups yourself --
  exactly the kind of judgment call that, if gotten wrong by a script,
  risks silently warping the fillet radius or a mounting hole, which
  would violate the "don't distort dimensions/functional geometry"
  requirement you've had throughout this project.
 
STEP-BY-STEP ONCE THE DIALOG IS OPEN
  1. Body: the script pre-selects it before opening the dialog, but when
     tested live this did NOT reliably carry into the command's own Body
     field (it showed 0 selected even after pre-selecting). So: check
     the Body field when the dialog opens, and if it's empty, click it
     and pick the body in the viewport/browser yourself.
  2. Operation: "New Body" (safe default -- keeps your original mesh body
     untouched alongside the new clean one, so you can compare/undo
     easily) or "New Component" if you'd rather it land in its own
     component. Avoid "Cut"/"Join"/"Intersect" here unless you
     specifically mean to combine it with another body.
  3. Method: change this to **Prismatic**.
  4. Fusion highlights the face groups it detected (flat regions vs. the
     curved fillet/boss). Check that the rounded corner and the boss are
     each captured as ONE cylindrical group, not split into several --
     if they look split, try adjusting the angle/tolerance slider Fusion
     shows for grouping (higher tolerance merges more facets into one
     group).
  5. Click OK. The striping should be gone -- that region is now a true
     cylindrical surface.
  6. Inspect the result: check the fillet radius and hole/boss diameter
     against your original spec (Inspect > Measure) before deleting the
     old mesh body, in case the auto-fit didn't match exactly and needs a
     manual fillet/hole feature instead for that one region.
 
HOW TO RUN
  Fusion 360 > Utilities tab > Scripts and Add-ins > "+" > select this
  file > Run. Select your faceted body in the model first, or the script
  will prompt you to pick it.
"""
 
import adsk.core
import adsk.fusion
import traceback
 
 
def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design: adsk.fusion.Design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox('No active Fusion design. Open/activate a design first.')
            return
 
        body = _resolve_body(ui)
        if body is None:
            return  # user cancelled
 
        planar_count = sum(1 for f in body.faces
                            if f.geometry.surfaceType == adsk.core.SurfaceTypes.PlaneSurfaceType)
        total = body.faces.count
        if total and planar_count / total > 0.9 and total > 50:
            note = (f'"{body.name}" looks like a faceted/mesh-derived body '
                     f'({planar_count} of {total} faces are flat micro-facets) '
                     '-- Convert Mesh is the right tool for this.')
        else:
            note = (f'"{body.name}" has {total} faces, {planar_count} planar. '
                     'This doesn\'t look strongly mesh-like -- double-check '
                     'this is the body you meant before converting it.')
 
        cmd_def = ui.commandDefinitions.itemById('ParaMeshConvertCommand')
        if cmd_def is None:
            ui.messageBox(
                f'{note}\n\n'
                'Could not find the Convert Mesh command in this Fusion '
                'version. Open it manually: Design workspace > Mesh tab > '
                'Modify > Convert, then select the body and set Method = '
                'Prismatic.'
            )
            return
 
        ui.messageBox(
            f'{note}\n\n'
            'Opening Convert Mesh (the body is pre-selected, but double '
            'check the Body field once the dialog is open -- in testing '
            'this didn\'t always carry through, so click it and pick the '
            'body yourself if it looks empty).\n\n'
            'IMPORTANT -- change Method from "Faceted" to "Prismatic" '
            '(this is what actually removes the facet striping -- '
            'Faceted leaves it as-is). Review the detected flat/'
            'cylindrical face groups, then click OK.\n\n'
            'Once this dialog opens, Fusion blocks all further scripting '
            'until you close it (a Fusion limitation, not this script) -- '
            'finish or cancel the dialog yourself in the app.'
        )
 
        ui.activeSelections.clear()
        ui.activeSelections.add(body)
        cmd_def.execute()
 
        # Keep the script alive long enough for the command to start.
        adsk.autoTerminate(False)
 
    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
 
 
def _resolve_body(ui: adsk.core.UserInterface):
    selections = ui.activeSelections
    if selections.count == 1:
        entity = selections.item(0).entity
        if entity.objectType == adsk.fusion.BRepBody.classType():
            return entity
 
    try:
        sel_input = ui.selectEntity('Select the faceted body to convert', 'Bodies')
    except RuntimeError:
        return None  # user pressed Escape / cancelled
    return sel_input.entity