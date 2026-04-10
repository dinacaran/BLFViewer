# Disclaimer

## General

This software is provided **"as is"**, without warranty of any kind, express or
implied, including but not limited to the warranties of merchantability, fitness
for a particular purpose, and non-infringement. In no event shall the authors or
copyright holders be liable for any claim, damages, or other liability — whether
in an action of contract, tort, or otherwise — arising from, out of, or in
connection with the software or the use or other dealings in the software.

## Intended Use — Offline Analysis Only

BLF Viewer is designed exclusively for **offline, post-processing analysis**
of recorded CAN measurement data.

- This tool **must not** be used for any safety-critical application.
- This tool **must not** be used for real-time vehicle control, diagnostics,
  or any other purpose that could affect vehicle behaviour.
- This tool **must not** be used in production, manufacturing, or
  certification workflows without independent validation.

## Proprietary Data Responsibility

DBC and BLF files may contain **proprietary OEM, Tier-1, or supplier data**
protected by confidentiality agreements or intellectual property law.

You are solely responsible for ensuring that:
- You have the legal right to use any BLF or DBC files loaded into this tool.
- You do not share, publish, or redistribute files containing proprietary data.
- Your use complies with any applicable NDAs or licensing agreements.

The authors of BLF Viewer accept no responsibility for unauthorised use or
disclosure of proprietary data processed by this tool.

## Third-Party Format and Library Notice

The Vector BLF (Binary Logging Format) is a proprietary file format owned by
**Vector Informatik GmbH**. This project is **not affiliated with, endorsed by,
or supported by Vector Informatik GmbH**.

BLF file support is provided through the open-source
[python-can](https://github.com/hardbyte/python-can) library, which implements
BLF reading independently of Vector's commercial software.

Signal decoding is provided through the open-source
[cantools](https://github.com/eerimoq/cantools) library.

Use of this tool does not replace or substitute Vector CANalyzer, CANdb++,
or any other Vector product.

## No Warranty on Decoding Accuracy

Signal decoding depends entirely on the correctness of the provided DBC file.
The authors make no guarantee that decoded values are accurate or complete.
Always validate critical signal values against a trusted reference tool.
