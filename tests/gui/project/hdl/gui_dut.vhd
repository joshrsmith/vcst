library ieee;
use ieee.std_logic_1164.all;

entity gui_dut is
port (
    clock : in std_logic;
    d     : in std_logic;
    q     : out std_logic
);
end entity gui_dut;

architecture rtl of gui_dut is
    -- Drives no port, so that an optimizing simulator could remove it: the test reads it, and so does run_once.do, as a
    -- user debugging in the GUI does
    signal not_d : std_logic;
begin
    q <= d when rising_edge(clock);
    not_d <= not d;
end architecture rtl;
