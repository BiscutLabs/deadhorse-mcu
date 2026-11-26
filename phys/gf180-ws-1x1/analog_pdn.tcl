# Local T43 adaptation: connect the actual lower Metal5 supply pins to
# a per-macro ring. The abstract generator checks the open Metal4 band.
# Extending to the ring is required: core-boundary stripes do not reach it.
define_pdn_grid -macro -instances {i_chip_core.soc.lf i_chip_core.soc.por} -name analog_access -grid_over_boundary -starts_with POWER -halo 0
add_pdn_ring -grid analog_access -layers {Metal4 Metal5} -widths 2 -spacings 2 -core_offsets 12
add_pdn_stripe -grid analog_access -layer Metal5 -width 2 -spacing 2 -pitch 500 -offset 1 -starts_with GROUND -number_of_straps 1 -extend_to_core_ring
add_pdn_connect -grid analog_access -layers {Metal4 Metal5}
add_pdn_connect -grid analog_access -layers {Metal1 Metal4}
