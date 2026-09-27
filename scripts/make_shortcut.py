"""Build an unsigned 'Wall Art.shortcut' (binary plist). Sign on macOS with:
   shortcuts sign -m anyone -i "Wall Art.unsigned.shortcut" -o "Wall Art.shortcut"
"""
import plistlib, uuid

import os
BASE_URL = os.environ.get("FRAMES_URL", "https://raw.githubusercontent.com/USER/tv-art-frames/main")
CANVAS_W, CANVAS_H = 2048, 1152
OBJ = "￼"


def var(name):
    return {"Value": {"Type": "Variable", "VariableName": name},
            "WFSerializationType": "WFTextTokenAttachment"}


def text(*parts):
    """parts: str or ('var', name). Returns a WFTextTokenString."""
    s, att = "", {}
    for p in parts:
        if isinstance(p, tuple):
            att[f"{{{len(s)}, 1}}"] = {"Type": "Variable", "VariableName": p[1]}
            s += OBJ
        else:
            s += p
    if not att:
        return s
    return {"Value": {"string": s, "attachmentsByRange": att},
            "WFSerializationType": "WFTextTokenString"}


def act(ident, **params):
    return {"WFWorkflowActionIdentifier": ident, "WFWorkflowActionParameters": params}


def setvar(name, inp=None):
    p = {"WFVariableName": name}
    if inp is not None:
        p["WFInput"] = inp
    return act("is.workflow.actions.setvariable", **p)


def getkey(dict_var, key, out):
    return [act("is.workflow.actions.getvalueforkey", WFInput=var(dict_var),
                WFDictionaryKey=key, WFGetDictionaryValueType="Value"),
            setvar(out)]


def geturl(url_text, out):
    return [act("is.workflow.actions.downloadurl", WFURL=url_text, WFHTTPMethod="GET"),
            setvar(out)]


def getfile(path_text, out):
    return [act("is.workflow.actions.documentpicker.open", WFGetFilePath=path_text,
                WFShowFilePicker=False, WFFileErrorIfNotFound=True),
            setvar(out)]



# ---------------------------------------------------------------- small builders
def uid():
    return str(uuid.uuid4()).upper()


def if_start(g, var_name, cond, **cmp):
    """cond: 2 = greater than (numbers, WFNumberValue), 4 = is (text: WFConditionalActionString / numbers: WFNumberValue)."""
    return act("is.workflow.actions.conditional", WFInput={"Type": "Variable", "Variable": var(var_name)},
               WFCondition=cond, GroupingIdentifier=g, WFControlFlowMode=0, **cmp)


def if_else(g):
    return act("is.workflow.actions.conditional", GroupingIdentifier=g, WFControlFlowMode=1)


def if_end(g):
    return act("is.workflow.actions.conditional", GroupingIdentifier=g, WFControlFlowMode=2)


def math(inp, op, operand, out):
    operand = text(("var", operand)) if isinstance(operand, str) else operand
    return [act("is.workflow.actions.math", WFInput=var(inp), WFMathOperation=op, WFMathOperand=operand), setvar(out)]


def resize(src, w, h, out):
    tv = lambda v: text(("var", v)) if isinstance(v, str) and v != "Auto" else (v if isinstance(v, str) else str(v))
    return [act("is.workflow.actions.image.resize", WFImage=var(src), WFInput=var(src),
                WFImageResizeWidth=tv(w), WFImageResizeHeight=tv(h)), setvar(out)]


def overlay(base, top, x, y, w, h, out, opacity="100"):
    tv = lambda v: text(("var", v)) if isinstance(v, str) else str(v)
    return [act("is.workflow.actions.overlayimageonimage", WFInput=var(base), WFImage=var(top),
                WFShouldShowImageEditor=False, WFImagePosition="Custom",
                WFImageX=tv(x), WFImageY=tv(y), WFImageWidth=tv(w), WFImageHeight=tv(h),
                WFRotation="0", WFOverlayImageOpacity=opacity), setvar(out)]


def img_prop(src, prop, out):
    return [act("is.workflow.actions.properties.images", WFInput=var(src), WFContentItemPropertyName=prop),
            setvar(out)]


def use_frame(img, x, y, w, h):
    """Which frame image and opening the finished photo goes into."""
    return [setvar("CurImg", var(img)), setvar("CX", var(x)), setvar("CY", var(y)),
            setvar("CW", var(w)), setvar("CH", var(h))]


def blur_fill(w, h, out):
    """Sdr zoomed to cover w x h, blurred (shrink + blend shifted copies), darkened -> out."""
    a = []
    a += math(w, "+", 112, "BgW") + math(h, "+", 112, "BgH")
    a += resize("Sdr", "BgW", "Auto", "BgWide")
    a += [act("is.workflow.actions.image.crop", WFInput=var("BgWide"), WFImageCropPosition="Center",
              WFImageCropWidth=text(("var", "BgW")), WFImageCropHeight=text(("var", "BgH"))), setvar("BgCrop")]
    a += resize("BgCrop", 30, "Auto", "BgTiny")
    a += resize("BgTiny", "BgW", "BgH", "Soft")
    for axis in ("x", "y"):
        for sh in (8, 16, 32):
            a += overlay("Soft", "Soft", sh if axis == "x" else 0, 0 if axis == "x" else sh, "BgW", "BgH",
                         "Soft", opacity="50")
    a += [act("is.workflow.actions.image.crop", WFInput=var("Soft"), WFImageCropPosition="Center",
              WFImageCropWidth=text(("var", w)), WFImageCropHeight=text(("var", h))), setvar("BgBlur")]
    a += overlay("BgBlur", "DimImage", 0, 0, w, h, out, opacity="60")
    return a


def whole_photo():
    """Whole photo, no crop. Mat frames: painted mat + bevel on the moulding-only frame.
    No-mat frames: blurred copy of the photo around it."""
    g = uid()
    a = [if_start(g, "Fill", 4, WFConditionalActionString="mat")]
    # --- mat fill ---
    a += geturl(text(f"{BASE_URL}/", ("var", "MatFile")), "Swatch")
    a += resize("Swatch", "FitW", "FitH", "MatBg")
    a += math("MatPx", "×", 2, "Mat2") + math("FitH", "-", "Mat2", "MainH")
    a += resize("Sdr", "Auto", "MainH", "Main")
    a += img_prop("Main", "Width", "MainW")
    a += math("FitW", "-", "MainW", "SideGap") + math("SideGap", "÷", 2, "SideHalf")
    a += [act("is.workflow.actions.round", WFInput=var("SideHalf"), WFRoundTo="Ones Place", WFRoundMode="Normal"),
          setvar("MX")]
    a += overlay("MatBg", "Main", "MX", "MatPx", "MainW", "MainH", "Comp")
    # bevel: 5 px bright line around the photo
    a += math("MX", "-", 5, "BvX") + math("MatPx", "-", 5, "BvY")
    a += math("MainW", "+", 10, "BvW") + math("MainH", "+", 10, "BvH")
    a += math("MX", "+", "MainW", "BvR") + math("MatPx", "+", "MainH", "BvB")
    a += overlay("Comp", "BevelImage", "BvX", "BvY", 5, "BvH", "Comp")     # left
    a += overlay("Comp", "BevelImage", "BvR", "BvY", 5, "BvH", "Comp")     # right
    a += overlay("Comp", "BevelImage", "BvX", "BvY", "BvW", 5, "Comp")     # top
    a += overlay("Comp", "BevelImage", "BvX", "BvB", "BvW", 5, "Comp")     # bottom
    a += overlay("Comp", "Main", "MX", "MatPx", "MainW", "MainH", "Cropped")   # photo back on top of the lines
    a += use_frame("FitImage", "FitX", "FitY", "FitW", "FitH")
    a += [if_else(g)]
    # --- blur fill (no-mat frames) ---
    a += blur_fill("W", "H", "Bg")
    a += resize("Sdr", "Auto", "H", "Main")
    a += img_prop("Main", "Width", "MainW")
    a += math("W", "-", "MainW", "SideGap") + math("SideGap", "÷", 2, "SideHalf")
    a += [act("is.workflow.actions.round", WFInput=var("SideHalf"), WFRoundTo="Ones Place", WFRoundMode="Normal"),
          setvar("MX")]
    a += overlay("Bg", "Main", "MX", 0, "MainW", "H", "Cropped")
    a += use_frame("FrameImage", "X", "Y", "W", "H")
    a += [if_end(g)]
    return a


# ---------------------------------------------------------------- the shortcut
actions = []
actions += [act("is.workflow.actions.comment",
                WFCommentActionText="Wall Art: pick a frame and photos, get framed 2048x1152 JPEGs for the TV. "
                                    "Frames are downloaded from the tv-art-frames GitHub repo.")]
# 1. frames.json (random query string so GitHub/iOS caches never serve a stale copy)
actions += [act("is.workflow.actions.number.random", WFRandomNumberMinimum=1, WFRandomNumberMaximum=999999999),
            setvar("Nonce")]
actions += geturl(text(f"{BASE_URL}/frames.json?t=", ("var", "Nonce")), "ManifestFile")
actions += [act("is.workflow.actions.detect.dictionary", WFInput=var("ManifestFile")), setvar("Manifest")]
actions += getkey("Manifest", "catalog", "Frames")
# 2. choose frame
actions += [act("is.workflow.actions.getvalueforkey", WFInput=var("Frames"),
                WFGetDictionaryValueType="All Keys"), setvar("FrameNames")]
actions += [act("is.workflow.actions.choosefromlist", WFInput=var("FrameNames"),
                WFChooseFromListActionPrompt="Choose a frame"), setvar("FrameName")]
actions += [act("is.workflow.actions.getvalueforkey", WFInput=var("Frames"),
                WFDictionaryKey=text(("var", "FrameName")), WFGetDictionaryValueType="Value"),
            setvar("Variants")]
# 2b. mat choice, only when the frame has more than one version
actions += [act("is.workflow.actions.getvalueforkey", WFInput=var("Variants"),
                WFGetDictionaryValueType="All Keys"), setvar("VariantNames")]
MAT = uid()
actions += [act("is.workflow.actions.count", WFCountType="Items", Input=var("VariantNames"), WFInput=var("VariantNames")),
            setvar("VariantCount"),
            if_start(MAT, "VariantCount", 2, WFNumberValue=1),
            act("is.workflow.actions.choosefromlist", WFInput=var("VariantNames"),
                WFChooseFromListActionPrompt="With or without mat?"), setvar("VariantName"),
            if_else(MAT),
            act("is.workflow.actions.getitemfromlist", WFInput=var("VariantNames"), WFItemSpecifier="First Item"),
            setvar("VariantName"),
            if_end(MAT)]
actions += [act("is.workflow.actions.getvalueforkey", WFInput=var("Variants"),
                WFDictionaryKey=text(("var", "VariantName")), WFGetDictionaryValueType="Value"),
            setvar("Frame")]
for k, out in [("file", "FileName"), ("x", "X"), ("y", "Y"), ("w", "W"), ("h", "H"), ("id", "FrameId"),
               ("fit", "Fit")]:
    actions += getkey("Frame", k, out)
for k, out in [("file", "FitFile"), ("x", "FitX"), ("y", "FitY"), ("w", "FitW"), ("h", "FitH"),
               ("fill", "Fill"), ("mat_px", "MatPx"), ("mat_file", "MatFile")]:
    actions += getkey("Fit", k, out)
# 3. load frame images
actions += geturl(text(f"{BASE_URL}/frames/", ("var", "FileName")), "FrameImage")
actions += geturl(text(f"{BASE_URL}/frames/", ("var", "FitFile")), "FitImage")
actions += geturl(f"{BASE_URL}/ui/dim.png", "DimImage")
actions += geturl(f"{BASE_URL}/ui/bevel.png", "BevelImage")
# 4. pick photos
actions += [act("is.workflow.actions.selectphoto", WFSelectMultiplePhotos=True), setvar("Photos")]
# 5. loop
grp = uid()
ORIENT = uid()
PICK = uid()
actions += [act("is.workflow.actions.repeat.each", WFInput=var("Photos"),
                GroupingIdentifier=grp, WFControlFlowMode=0)]
# HDR photos wash out when composited; flatten to an SDR JPEG first
actions += [act("is.workflow.actions.image.convert", WFInput=var("Repeat Item"), WFImageFormat="JPEG",
                WFImageCompressionQuality=1.0, WFImagePreserveMetadata=False), setvar("Sdr")]
actions += img_prop("Sdr", "Width", "PhotoW") + img_prop("Sdr", "Height", "PhotoH")
actions += math("PhotoH", "-", "PhotoW", "Diff")
actions += [if_start(ORIENT, "Diff", 2, WFNumberValue=0)]
# ---- VERTICAL: always the whole photo
actions += whole_photo()
actions += [if_else(ORIENT)]
# ---- HORIZONTAL: five crop options + "whole photo" as option 6
actions += resize("Sdr", "W", "Auto", "Scaled")
actions += img_prop("Scaled", "Height", "ScaledH") + math("ScaledH", "-", "H", "Extra")
# darken the whole photo once; each crop option lays its band back on top at full brightness
actions += overlay("Scaled", "DimImage", 0, 0, "W", "ScaledH", "Dimmed")
for i, frac in enumerate([0, 0.25, 0.5, 0.75, 1.0], start=1):
    actions += [act("is.workflow.actions.math", WFInput=var("Extra"), WFMathOperation="×", WFMathOperand=frac),
                act("is.workflow.actions.round", WFRoundTo="Ones Place", WFRoundMode="Normal"), setvar("OffY"),
                act("is.workflow.actions.image.crop", WFInput=var("Scaled"), WFImageCropPosition="Custom",
                    WFImageCropX="0", WFImageCropY=text(("var", "OffY")),
                    WFImageCropWidth=text(("var", "W")), WFImageCropHeight=text(("var", "H"))),
                setvar("Piece")]
    actions += overlay("Dimmed", "Piece", 0, "OffY", "W", "H", "Preview")
    # tag the option in the image itself: option i is i pixels narrower than the window
    # (names don't survive Choose from List; pixel sizes do)
    actions += math("W", "-", i, "PW") + resize("Preview", "PW", "Auto", "Candidate")
    actions += [setvar("Choices", var("Candidate")) if i == 1 else
                act("is.workflow.actions.appendvariable", WFInput=var("Candidate"), WFVariableName="Choices")]
# option 6: the whole photo, undimmed
actions += math("W", "-", 6, "PW") + resize("Scaled", "PW", "Auto", "Candidate")
actions += [act("is.workflow.actions.appendvariable", WFInput=var("Candidate"), WFVariableName="Choices")]
actions += [act("is.workflow.actions.choosefromlist", WFInput=var("Choices"),
                WFChooseFromListActionPrompt="Pick a crop (last one = whole photo)"), setvar("Chosen")]
actions += img_prop("Chosen", "Width", "ChosenW") + math("W", "-", "ChosenW", "Idx")
actions += [if_start(PICK, "Idx", 4, WFNumberValue=6)]
actions += whole_photo()
actions += [if_else(PICK)]
actions += math("Idx", "-", 1, "Step") + math("Step", "×", "Extra", "Scaled4")
actions += [act("is.workflow.actions.math", WFInput=var("Scaled4"), WFMathOperation="÷", WFMathOperand=4),
            act("is.workflow.actions.round", WFRoundTo="Ones Place", WFRoundMode="Normal"), setvar("FinalY"),
            act("is.workflow.actions.image.crop", WFInput=var("Scaled"), WFImageCropPosition="Custom",
                WFImageCropX="0", WFImageCropY=text(("var", "FinalY")),
                WFImageCropWidth=text(("var", "W")), WFImageCropHeight=text(("var", "H"))),
            setvar("Cropped")]
actions += use_frame("FrameImage", "X", "Y", "W", "H")
actions += [if_end(PICK)]
actions += [if_end(ORIENT)]
# ---- put it in the frame
actions += overlay("CurImg", "Cropped", "CX", "CY", "CW", "CH", "Framed")
actions += overlay("Framed", "CurImg", 0, 0, CANVAS_W, CANVAS_H, "Finished")
actions += [act("is.workflow.actions.image.convert", WFInput=var("Finished"), WFImageFormat="JPEG",
                WFImageCompressionQuality=0.9, WFImagePreserveMetadata=False), setvar("Jpeg"),
            act("is.workflow.actions.setitemname", WFInput=var("Jpeg"),
                WFName=text("TVArt-", ("var", "FrameId")), WFDontIncludeFileExtension=False),
            setvar("Named"),
            act("is.workflow.actions.appendvariable", WFInput=var("Named"), WFVariableName="Results")]
actions += [act("is.workflow.actions.repeat.each", GroupingIdentifier=grp, WFControlFlowMode=2)]
# 6. preview
actions += [act("is.workflow.actions.previewdocument", WFInput=var("Results"))]
# 7. optional save; using the shortcut's own save step makes iOS ask for Photos permission the first time
actions += [act("is.workflow.actions.gettext", WFTextActionText="Save to Photos\nDone"),
            act("is.workflow.actions.text.split", WFTextSeparator="New Lines"),
            setvar("FinishOptions"),
            act("is.workflow.actions.choosefromlist", WFInput=var("FinishOptions"),
                WFChooseFromListActionPrompt="Save the framed images to Photos?"),
            setvar("Finish")]
ifg = str(uuid.uuid4()).upper()
actions += [act("is.workflow.actions.conditional", WFInput={"Type": "Variable", "Variable": var("Finish")},
                WFCondition=4, WFConditionalActionString="Save to Photos",
                GroupingIdentifier=ifg, WFControlFlowMode=0),
            act("is.workflow.actions.savetocameraroll", WFInput=var("Results")),
            act("is.workflow.actions.conditional", GroupingIdentifier=ifg, WFControlFlowMode=2)]

# Wire every "Set variable" without an explicit input to the previous action's output.
for i, a in enumerate(actions):
    p = a["WFWorkflowActionParameters"]
    if a["WFWorkflowActionIdentifier"] in ("is.workflow.actions.setvariable", "is.workflow.actions.round",
                                           "is.workflow.actions.setitemname", "is.workflow.actions.text.replace",
                                           "is.workflow.actions.text.split") and "WFInput" not in p:
        prev = actions[i - 1]["WFWorkflowActionParameters"]
        prev.setdefault("UUID", str(uuid.uuid4()).upper())
        p["WFInput"] = {"Value": {"Type": "ActionOutput", "OutputUUID": prev["UUID"],
                                  "OutputName": p.get("WFVariableName", "Result")},
                        "WFSerializationType": "WFTextTokenAttachment"}

wf = {
    "WFWorkflowActions": actions,
    "WFWorkflowClientVersion": "2605.0.5",
    "WFWorkflowMinimumClientVersion": 900,
    "WFWorkflowMinimumClientVersionString": "900",
    "WFWorkflowIcon": {"WFWorkflowIconStartColor": 4292093695, "WFWorkflowIconGlyphNumber": 59784},  # green, "picture",
    "WFWorkflowImportQuestions": [],
    "WFWorkflowInputContentItemClasses": ["WFImageContentItem"],
    "WFWorkflowTypes": ["NCWidget", "WatchKit"],
    "WFWorkflowHasShortcutInputVariables": False,
    "WFQuickActionSurfaces": [],
}
with open("Wall Art.unsigned.shortcut", "wb") as fh:
    plistlib.dump(wf, fh, fmt=plistlib.FMT_BINARY)
print(len(actions), "actions")
