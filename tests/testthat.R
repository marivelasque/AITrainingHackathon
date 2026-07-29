# Run all tests from the project root: Rscript tests/testthat.R
library(testthat)
source("R/db.R")
test_dir("tests/testthat")
