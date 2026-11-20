library ieee;
use ieee.std_logic_1164.all;

package names_pkg is
    type addr_array is array (natural range <>) of std_logic_vector(15 downto 0);
    type mode_t is (SLOW, FAST);
    type modes_t is record
        first   : mode_t;
        second  : mode_t;
    end record;
end package names_pkg;
