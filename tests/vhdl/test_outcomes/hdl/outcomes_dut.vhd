library ieee;
use ieee.std_logic_1164.all;

entity outcomes_dut is
port (
    clock   : in std_logic;
    d       : in std_logic;
    q       : out std_logic;
    -- Ends the simulation with an assertion failure when set
    trigger_failure : in std_logic := '0'
);
end entity outcomes_dut;

architecture rtl of outcomes_dut is
begin
    q <= d when rising_edge(clock);

    process (trigger_failure)
    begin
        assert trigger_failure /= '1' report "assertion failure triggered by the test" severity failure;
    end process;
end architecture rtl;
