--A VUnit test bench, which needs VUnit's VHDL builtins
library vunit_lib;
context vunit_lib.vunit_context;

entity tb_front_end is
generic (
    runner_cfg  : string
);
end entity tb_front_end;

architecture tb of tb_front_end is
begin
    test_runner: process
    begin
        test_runner_setup(runner, runner_cfg);

        while test_suite loop
            if run("vhdl_test") then
                check_equal(1 + 1, 2);
            end if;
        end loop;

        test_runner_cleanup(runner);
    end process test_runner;
end architecture tb;
