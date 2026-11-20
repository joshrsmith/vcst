library ieee;
use ieee.std_logic_1164.all;

entity front_end_dut is
port (
    clock   : in std_logic;
    d       : in std_logic;
    q       : out std_logic
);
end entity front_end_dut;

architecture rtl of front_end_dut is
begin
    q <= d when rising_edge(clock);
end architecture rtl;
