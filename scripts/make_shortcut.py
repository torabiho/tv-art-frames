"""Build an unsigned 'Frame for TV.shortcut' (binary plist). Sign on macOS with:
   shortcuts sign -m anyone -i "Frame for TV.unsigned.shortcut" -o "Frame for TV.shortcut"
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


actions = []
actions += [act("is.workflow.actions.comment",
                WFCommentActionText="Frame for TV: pick a frame and photos, get framed 2048x1152 JPEGs to add to the TV Art shared album. Frames are downloaded from the TV Art Frames GitHub repo.")]
# 1. frames.json -> dictionary
actions += geturl(f"{BASE_URL}/frames.json", "ManifestFile")
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
# 2b. mat choice; a frame with a single variant is picked automatically, no question shown
actions += [act("is.workflow.actions.getvalueforkey", WFInput=var("Variants"),
                WFGetDictionaryValueType="All Keys"), setvar("VariantNames")]
actions += [act("is.workflow.actions.choosefromlist", WFInput=var("VariantNames"),
                WFChooseFromListActionPrompt="With or without mat?"), setvar("VariantName")]
actions += [act("is.workflow.actions.getvalueforkey", WFInput=var("Variants"),
                WFDictionaryKey=text(("var", "VariantName")), WFGetDictionaryValueType="Value"),
            setvar("Frame")]
for k, out in [("file", "FileName"), ("x", "X"), ("y", "Y"), ("w", "W"), ("h", "H"), ("id", "FrameId")]:
    actions += getkey("Frame", k, out)
# 3. load frame images
actions += geturl(text(f"{BASE_URL}/frames/", ("var", "FileName")), "FrameImage")
actions += geturl(f"{BASE_URL}/ui/dim.png", "DimImage")
# 4. pick photos
actions += [act("is.workflow.actions.selectphoto", WFSelectMultiplePhotos=True), setvar("Photos")]
# 5. loop
grp = str(uuid.uuid4()).upper()
actions += [act("is.workflow.actions.repeat.each", WFInput=var("Photos"),
                GroupingIdentifier=grp, WFControlFlowMode=0)]
actions += [
    # every frame window is wider than 16:9, so fit-to-width then centre-crop fills it
    # HDR photos (10-bit HLG / Display P3) wash out when composited; flatten to an SDR JPEG first
    act("is.workflow.actions.image.convert", WFInput=var("Repeat Item"), WFImageFormat="JPEG",
        WFImageCompressionQuality=1.0, WFImagePreserveMetadata=False),
    setvar("Sdr"),
    act("is.workflow.actions.image.resize", WFImage=var("Sdr"), WFInput=var("Sdr"),
        WFImageResizeWidth=text(("var", "W")), WFImageResizeHeight="Auto"),
    setvar("Scaled"),
    # --- five crop candidates from top to bottom; the user picks one by thumbnail ---
    act("is.workflow.actions.properties.images", WFInput=var("Scaled"), WFContentItemPropertyName="Height"),
    setvar("ScaledH"),
    act("is.workflow.actions.math", WFInput=var("ScaledH"), WFMathOperation="-", WFMathOperand=text(("var", "H"))),
    setvar("Extra"),
    # darken the whole photo once; each option lays its crop back on top at full brightness
    act("is.workflow.actions.overlayimageonimage", WFInput=var("Scaled"), WFImage=var("DimImage"),
            WFShouldShowImageEditor=False, WFImagePosition="Custom",
            WFImageX="0", WFImageY="0", WFImageWidth=text(("var", "W")), WFImageHeight=text(("var", "ScaledH")),
            WFRotation="0", WFOverlayImageOpacity="100"),
    setvar("Dimmed"),
]
for i, frac in enumerate([0, 0.25, 0.5, 0.75, 1.0], start=1):
    actions += [
        act("is.workflow.actions.math", WFInput=var("Extra"), WFMathOperation="×", WFMathOperand=frac),
        act("is.workflow.actions.round", WFRoundTo="Ones Place", WFRoundMode="Normal"),
        setvar("OffY"),
        act("is.workflow.actions.image.crop", WFInput=var("Scaled"), WFImageCropPosition="Custom",
            WFImageCropX="0", WFImageCropY=text(("var", "OffY")),
            WFImageCropWidth=text(("var", "W")), WFImageCropHeight=text(("var", "H"))),
        setvar("Piece"),
        act("is.workflow.actions.overlayimageonimage", WFInput=var("Dimmed"), WFImage=var("Piece"),
            WFShouldShowImageEditor=False, WFImagePosition="Custom",
            WFImageX="0", WFImageY=text(("var", "OffY")), WFImageWidth=text(("var", "W")), WFImageHeight=text(("var", "H")),
            WFRotation="0", WFOverlayImageOpacity="100"),
        act("is.workflow.actions.setitemname", WFName=f"Option {i}", WFDontIncludeFileExtension=False),
        setvar("Candidate"),
        setvar("Choices", var("Candidate")) if i == 1 else
        act("is.workflow.actions.appendvariable", WFInput=var("Candidate"), WFVariableName="Choices"),
    ]
actions += [
    act("is.workflow.actions.choosefromlist", WFInput=var("Choices"),
        WFChooseFromListActionPrompt="Pick the crop that fits best"),
    setvar("Chosen"),
    act("is.workflow.actions.getitemname", WFInput=var("Chosen")),
    act("is.workflow.actions.text.replace", WFReplaceTextFind="Option ", WFReplaceTextReplace=""),
    setvar("Idx"),
    act("is.workflow.actions.math", WFInput=var("Idx"), WFMathOperation="-", WFMathOperand=1),
    setvar("Step"),
    act("is.workflow.actions.math", WFInput=var("Step"), WFMathOperation="\u00d7", WFMathOperand=text(("var", "Extra"))),
    setvar("Scaled4"),
    act("is.workflow.actions.math", WFInput=var("Scaled4"), WFMathOperation="\u00f7", WFMathOperand=4),
    act("is.workflow.actions.round", WFRoundTo="Ones Place", WFRoundMode="Normal"),
    setvar("FinalY"),
    act("is.workflow.actions.image.crop", WFInput=var("Scaled"), WFImageCropPosition="Custom",
        WFImageCropX="0", WFImageCropY=text(("var", "FinalY")),
        WFImageCropWidth=text(("var", "W")), WFImageCropHeight=text(("var", "H"))),
    setvar("Cropped"),
    act("is.workflow.actions.overlayimageonimage", WFInput=var("FrameImage"), WFImage=var("Cropped"),
        WFShouldShowImageEditor=False, WFImagePosition="Custom",
        WFImageX=text(("var", "X")), WFImageY=text(("var", "Y")),
        WFImageWidth=text(("var", "W")), WFImageHeight=text(("var", "H")),
        WFRotation="0", WFOverlayImageOpacity="100"),
    setvar("Framed"),
    act("is.workflow.actions.overlayimageonimage", WFInput=var("Framed"), WFImage=var("FrameImage"),
        WFShouldShowImageEditor=False, WFImagePosition="Custom",
        WFImageX="0", WFImageY="0", WFImageWidth=str(CANVAS_W), WFImageHeight=str(CANVAS_H),
        WFRotation="0", WFOverlayImageOpacity="100"),
    setvar("Finished"),
    act("is.workflow.actions.image.convert", WFInput=var("Finished"), WFImageFormat="JPEG",
        WFImageCompressionQuality=0.9, WFImagePreserveMetadata=False),
    setvar("Jpeg"),
    act("is.workflow.actions.setitemname", WFInput=var("Jpeg"),
        WFName=text("TVArt-", ("var", "FrameId")), WFDontIncludeFileExtension=False),
    setvar("Named"),
    act("is.workflow.actions.appendvariable", WFInput=var("Named"), WFVariableName="Results"),
]
actions += [act("is.workflow.actions.repeat.each", GroupingIdentifier=grp, WFControlFlowMode=2)]
# 6. hand back
actions += [act("is.workflow.actions.previewdocument", WFInput=var("Results"))]

# Wire every "Set variable" without an explicit input to the previous action's output.
for i, a in enumerate(actions):
    p = a["WFWorkflowActionParameters"]
    if a["WFWorkflowActionIdentifier"] in ("is.workflow.actions.setvariable", "is.workflow.actions.round",
                                           "is.workflow.actions.setitemname", "is.workflow.actions.text.replace") and "WFInput" not in p:
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
    "WFWorkflowIcon": {"WFWorkflowIconStartColor": 463140863, "WFWorkflowIconGlyphNumber": 59511},
    "WFWorkflowImportQuestions": [],
    "WFWorkflowInputContentItemClasses": ["WFImageContentItem"],
    "WFWorkflowTypes": ["NCWidget", "WatchKit"],
    "WFWorkflowHasShortcutInputVariables": False,
    "WFQuickActionSurfaces": [],
}
with open("Frame for TV.unsigned.shortcut", "wb") as fh:
    plistlib.dump(wf, fh, fmt=plistlib.FMT_BINARY)
print(len(actions), "actions")
