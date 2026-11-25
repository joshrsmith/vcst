#Uses VUnitCLI with an argument of its own and from_args, and adds the VHDL builtins although VCST already did
from pathlib import Path
import os
from vunit import VUnitCLI
from vcst import VCST

root = Path(os.path.abspath(Path(__file__).parent))

cli = VUnitCLI()
cli.parser.add_argument("--require-custom", action="store_true", help="Fail unless this option is given")
cli.parser.add_argument("--seed-option", help="Value of the seed simulation option (VUnit 5)")
args = cli.parse_args()
if not args.require_custom:
    raise SystemExit("--require-custom was not given")

ui = VCST.from_args(args=args)
ui.add_vhdl_builtins()
lib = ui.add_library("lib")
lib.add_source_files(root / "hdl" / "*.vhd", vhdl_standard="2008")
ui.add_cocotb_testbench(root / "test_front_end")
if args.seed_option is not None:
    ui.set_sim_option("seed", args.seed_option)
ui.main()
