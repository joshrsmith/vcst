library ieee;
use ieee.std_logic_1164.all;

entity dut_a is
port (
    clock   : in std_logic;
    q       : out std_logic
);
end entity dut_a;

architecture rtl of dut_a is
begin
    q <= clock;
end architecture rtl;

library ieee;
use ieee.std_logic_1164.all;

entity dut_b is
port (
    clock   : in std_logic;
    q       : out std_logic
);
end entity dut_b;

architecture rtl of dut_b is
begin
    q <= not clock;
end architecture rtl;
