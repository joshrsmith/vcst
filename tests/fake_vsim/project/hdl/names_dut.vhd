library ieee;
use ieee.std_logic_1164.all;
use work.names_pkg.all;

entity names_dut is
generic (
    WIDTH   : positive := 8;
    LABEL   : string := "default";
    FILE_NAME : string := "default";
    INIT    : std_logic_vector(15 downto 0) := (others => '0');
    BIT     : std_logic := '0';
    MODE    : mode_t := SLOW;
    MODES   : modes_t := (SLOW, SLOW);
    MORE_MODES : modes_t := (SLOW, SLOW);
    ADDRS   : addr_array := (0 => x"0000")
);
port (
    clock   : in std_logic;
    d       : in std_logic;
    q       : out std_logic
);
end entity names_dut;

architecture rtl of names_dut is
begin
    q <= d when rising_edge(clock);
end architecture rtl;
