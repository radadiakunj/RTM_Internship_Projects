"""
Fusion 360 Script: Select-and-Reduce Helper
--------------------------------------------
WHAT THIS DOES
This script automates the tedious PICKING part of mesh cleanup so you never
have to click individual triangles:
 
  1. Scans the active design for mesh bodies (the output of "Convert to Mesh").
  2. Reports each mesh body's current triangle/face count and rough size, so
     you know how aggressive to be.
  3. Lets you pick which mesh body to clean (or auto-picks if there's only one).
  4. Automatically selects that body and launches Fusion's native "Reduce"
     command with it pre-selected, so you land straight on the settings
     dialog instead of hunting through the Mesh tab and re-selecting.
 
WHY IT DOESN'T DO THE REDUCTION MATH ITSELF
Fusion's API does not currently expose a supported, documented way to set
the numeric parameters of the Reduce/Remesh commands programmatically or to
push a new decimated triangle set back into a mesh body (see the companion
README for details and sources). The only public, stable entry point is the
same "Reduce" dialog you'd use by hand -- so this script gets you to that
dialog with zero manual selection, and you enter your target (Face Count /
Proportion / Tolerance) once, exactly as request #8 (user-controllable
detail level) asks for.
 
For a FULLY automated / batch / precisely-repeatable reduction pipeline
(no dialogs at all), use script 2_pymeshlab_reduce.py instead, which runs
outside Fusion and preserves boundaries, sharp edges and holes reliably --
then re-import the result with Insert > Insert Mesh.
 
HOW TO RUN
  Fusion 360 > Utilities tab > Scripts and Add-ins > "+" > select this file
  > Run. Make sure a design containing at least one mesh body (from
  Convert to Mesh) is the active document first.
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
 
        root = design.rootComponent
 
        # Collect candidate bodies. NOTE: "Convert to Mesh" in current
        # Fusion versions produces a body that shows up in bRepBodies, not
        # the separate meshBodies collection (meshBodies seems reserved for
        # bodies that came in via Insert Mesh / STL import). So we scan
        # BOTH collections and let the name/heuristic tell them apart, and
        # show the type in the picker so it's unambiguous.
        mesh_bodies = []
 
        def collect(comp):
            for body in comp.meshBodies:
                mesh_bodies.append((body, 'Mesh'))
            for body in comp.bRepBodies:
                is_mesh_like = 'mesh' in body.name.lower()
                mesh_bodies.append((body, 'Mesh-like BRep' if is_mesh_like else 'Solid BRep'))
 
        collect(root)
        for occ in root.allOccurrences:
            collect(occ.component)
 
        if not mesh_bodies:
            ui.messageBox(
                'No bodies at all found in this design.\n\n'
                'Run "Modify > Convert to Mesh" on your solid first, '
                'then run this script again.'
            )
            return
 
        # Report triangle counts so the user knows what they're dealing with.
        report_lines = []
        for i, (body, kind) in enumerate(mesh_bodies):
            tri_count = _safe_triangle_count(body)
            report_lines.append(f'  [{i}] ({kind}) "{body.name}"  -  ~{tri_count:,} triangles')
 
        if len(mesh_bodies) == 1:
            target, kind = mesh_bodies[0]
        else:
            choice = ui.inputBox(
                'Bodies found in this design:\n' + '\n'.join(report_lines) +
                '\n\nEnter the index number of the body to clean up '
                '(pick the one shown as "Mesh" or "Mesh-like BRep" -- '
                'that is your Convert to Mesh output):',
                'Select Body',
                '0'
            )
            text, cancelled = choice
            if cancelled:
                return
            try:
                idx = int(text.strip())
                target, kind = mesh_bodies[idx]
            except (ValueError, IndexError):
                ui.messageBox('Invalid index. Re-run the script and try again.')
                return
 
        tri_count = _safe_triangle_count(target)
        ui.messageBox(
            f'Selected body: "{target.name}" ({kind})\n'
            f'Current triangle count: ~{tri_count:,}\n\n'
            'Opening the Reduce dialog with this body pre-selected.\n\n'
            'Recommended settings for 3D-printing prep:\n'
            '  - Reduction Type: Proportion (start ~50-70% of original) or\n'
            '    Face Count if you have a specific triangle budget\n'
            '  - Remesh Type: Adaptive (keeps detail on curves/holes, thins\n'
            '    out large flat faces) -- use Uniform only if you need an\n'
            '    even triangle grid for FEA/slicing reasons\n'
            '  - Turn on Preview and dial it back if edges/holes blur out'
        )
 
        # Select the body, then invoke the native Reduce command with it
        # pre-selected -- this is the supported, stable way to hand off
        # into the dialog without any manual triangle picking.
        ui.activeSelections.clear()
        ui.activeSelections.add(target)
 
        reduce_cmd_def = ui.commandDefinitions.itemById('ReduceCommand')
        if reduce_cmd_def is None:
            # Command id can vary slightly by Fusion version; fall back to
            # telling the user exactly where to click.
            ui.messageBox(
                'Body is selected. Now open it manually:\n'
                'Design workspace > Mesh tab > Modify > Reduce'
            )
            return
 
        reduce_cmd_def.execute()
 
        # Keep the script alive long enough for the command to start.
        adsk.autoTerminate(False)
 
    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
 
 
def _safe_triangle_count(mesh_body: adsk.fusion.MeshBody) -> int:
    try:
        mesh = mesh_body.displayMesh
        if mesh and mesh.nodeIndices:
            return len(mesh.nodeIndices) // 3
    except Exception:
        pass
    return -1