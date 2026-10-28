#!/usr/bin/env python3
"""Build a fake sysfs tree from the 9070 XT's real files, for htop-fake (see build-htop-fake.sh).

Usage: python3 -I fake-sysfs.py <root> [--suspended] [--unbind] [--remove PATH ...] [--write PATH=VALUE ...]
PATH is relative to the card's device dir and may use globs, e.g. 'hwmon/*/power1_cap'.
The tree is rebuilt from scratch on every run.
"""
import argparse, glob, importlib.util, os, shutil, sys

sys.dont_write_bytecode = True  # keep tools/ free of __pycache__
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("test_sampler", os.path.join(HERE, "test-sampler.py"))
test_sampler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(test_sampler)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("root")
    p.add_argument("--suspended", action="store_true", help="card reports runtime_status suspended")
    p.add_argument("--unbind", action="store_true", help="card not bound to amdgpu (meters: N/A)")
    p.add_argument("--remove", nargs="+", default=[], metavar="PATH")
    p.add_argument("--write", nargs="+", default=[], metavar="PATH=VALUE")
    args = p.parse_args()

    root = os.path.abspath(args.root)
    shutil.rmtree(root, ignore_errors=True)
    test_sampler.snapshot(root)
    dev = f"{root}/bus/pci/devices/{test_sampler.PCI}"

    if args.suspended:
        test_sampler.write(f"{dev}/power/runtime_status", "suspended\n")
    if args.unbind:
        os.remove(f"{root}/bus/pci/drivers/amdgpu/{test_sampler.PCI}")
    for pattern in args.remove:
        matches = glob.glob(f"{dev}/{pattern}")
        if not matches:
            sys.exit(f"--remove {pattern}: no such file")
        for path in matches:
            shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
    for item in args.write:
        pattern, _, value = item.partition("=")
        matches = glob.glob(f"{dev}/{pattern}")
        if not matches:
            sys.exit(f"--write {pattern}: no such file")
        for path in matches:
            test_sampler.write(path, value + "\n")
    print(root)


if __name__ == "__main__":
    main()
