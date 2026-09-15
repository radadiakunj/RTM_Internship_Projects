"""
Diagnostic Script
------------------
Run this in Fusion the same way as the other script (Utilities > Scripts
and Add-ins > + > select this file > Run). It prints out everything
Fusion sees in the ACTIVE document: which document is active, every
component, and every body in each component with its type (solid vs
mesh) and name. This tells us exactly why the reducer script isn't
finding your converted mesh.
"""
 
import adsk.core
import adsk.fusion
import traceback
 
 
def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
 
        lines = []
        lines.append(f"Active document: {app.activeDocument.name if app.activeDocument else 'NONE'}")
 
        product = app.activeProduct
        lines.append(f"Active product type: {product.classType() if product else 'NONE'}")
 
        design = adsk.fusion.Design.cast(product)
        if not design:
            ui.messageBox("Active product is NOT a Design (it's a "
                           f"{product.classType() if product else 'None'}).\n"
                           "Make sure the Fusion tab with your model is the "
                           "active/focused tab, and that you're in the "
                           "Design workspace.")
            return
 
        lines.append(f"Design type: {design.designType}")  # Parametric / DirectDesign
        try:
            tl = design.timeline
            lines.append(f"Timeline: {tl.count} items, marker at position {tl.markerPosition} "
                          f"(should equal {tl.count} if rolled to the end)")
        except Exception as e:
            lines.append(f"Timeline: not available ({e})")
 
        root = design.rootComponent
 
        def dump_component(comp, depth=0):
            indent = "  " * depth
            lines.append(f"{indent}Component: '{comp.name}'")
            lines.append(f"{indent}  bRepBodies (solid): {comp.bRepBodies.count}")
            for b in comp.bRepBodies:
                lines.append(f"{indent}    - '{b.name}' (visible={b.isVisible})")
            lines.append(f"{indent}  meshBodies (mesh): {comp.meshBodies.count}")
            for mb in comp.meshBodies:
                tri = -1
                try:
                    if mb.displayMesh and mb.displayMesh.nodeIndices:
                        tri = len(mb.displayMesh.nodeIndices) // 3
                except Exception:
                    pass
                lines.append(f"{indent}    - '{mb.name}' (visible={mb.isVisible}, ~{tri} tris)")
 
        dump_component(root)
        for occ in root.allOccurrences:
            dump_component(occ.component, depth=1)
 
        report = "\n".join(lines)
        print(report)
        ui.messageBox(report[:4000])  # messageBox has a rough length limit
 
    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))