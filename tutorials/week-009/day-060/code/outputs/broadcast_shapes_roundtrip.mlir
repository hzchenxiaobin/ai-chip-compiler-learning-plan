module {
  func.func @bc_row() -> !shape.shape {
    %0 = shape.const_shape [2, 3] : !shape.shape
    %1 = shape.const_shape [3] : !shape.shape
    %2 = shape.broadcast %0, %1 : !shape.shape, !shape.shape -> !shape.shape
    return %2 : !shape.shape
  }
  func.func @bc_bias() -> !shape.shape {
    %0 = shape.const_shape [8, 1000, 256] : !shape.shape
    %1 = shape.const_shape [256] : !shape.shape
    %2 = shape.broadcast %0, %1 : !shape.shape, !shape.shape -> !shape.shape
    return %2 : !shape.shape
  }
  func.func @bc_conflict() -> !shape.shape {
    %0 = shape.const_shape [2, 3] : !shape.shape
    %1 = shape.const_shape [4] : !shape.shape
    %2 = shape.broadcast %0, %1 : !shape.shape, !shape.shape -> !shape.shape
    return %2 : !shape.shape
  }
}

