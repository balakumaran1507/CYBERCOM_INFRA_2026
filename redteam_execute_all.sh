#!/bin/bash
################################################################################
# CYBERCOM Phase 2 - Red Team Assessment Suite
# Executes all adversarial security tests
################################################################################

echo "================================================================================"
echo "   CYBERCOM ADVERSARIAL SECURITY ENGINE - RED TEAM ASSESSMENT"
echo "================================================================================"
echo ""
echo "Executing comprehensive security penetration tests..."
echo "Target: Phase 2 Intelligence Layer"
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Results tracking
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

run_test() {
    local test_name=$1
    local test_file=$2

    echo ""
    echo "================================================================================    echo -e "${YELLOW}EXECUTING: $test_name${NC}"
    echo "================================================================================"
    echo ""

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    if docker compose exec ctfd python "$test_file" 2>&1 | tee "/tmp/redteam_${test_name}.log"; then
        echo ""
        echo -e "${GREEN}✓ Test completed${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo ""
        echo -e "${RED}✗ Test encountered errors${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi

    echo ""
    echo "Press ENTER to continue to next test (or Ctrl+C to abort)..."
    read
}

# Category A: First Blood Exploits
echo "================================================================================"
echo "CATEGORY A: FIRST BLOOD EXPLOITATION ATTACKS"
echo "================================================================================"

run_test "A1_Timestamp_Collision" "redteam_a1_timestamp_collision.py"
run_test "A2_Distributed_Race" "redteam_a2_distributed_race.py"

# Category B: GDPR Consent Bypass
echo "================================================================================"
echo "CATEGORY B: GDPR CONSENT BYPASS ATTACKS"
echo "================================================================================"

run_test "B1_Consent_Race" "redteam_b1_consent_race.py"

# Category C: Audit Trail Manipulation
echo "================================================================================"
echo "CATEGORY C: AUDIT TRAIL MANIPULATION ATTACKS"
echo "================================================================================"

run_test "C1_Verdict_Tampering" "redteam_c1_verdict_tampering.py"

# Category D: Redis Cache Integrity
echo "================================================================================"
echo "CATEGORY D: REDIS CACHE INTEGRITY ATTACKS"
echo "================================================================================"

run_test "D1_HMAC_Forgery" "redteam_d1_hmac_forgery.py"

# Category E: Worker Resource Exhaustion
echo "================================================================================"
echo "CATEGORY E: WORKER RESOURCE EXHAUSTION ATTACKS"
echo "================================================================================"

run_test "E1_Worker_DoS" "redteam_e1_worker_dos.py"

# Category F: Multi-Vector Combination
echo "================================================================================"
echo "CATEGORY F: MULTI-VECTOR COMBINATION ATTACKS"
echo "================================================================================"

run_test "F1_Combined_Attack" "redteam_f1_combined_attack.py"

# Final Report
echo ""
echo "================================================================================"
echo "                      RED TEAM ASSESSMENT COMPLETE"
echo "================================================================================"
echo ""
echo "Total Tests Executed: $TOTAL_TESTS"
echo "Completed Successfully: $PASSED_TESTS"
echo "Encountered Errors: $FAILED_TESTS"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}✓ All adversarial tests completed${NC}"
else
    echo -e "${YELLOW}⚠ Some tests encountered errors - review logs${NC}"
fi

echo ""
echo "Individual test logs saved to /tmp/redteam_*.log"
echo ""
echo "================================================================================"
echo "NEXT STEPS:"
echo "================================================================================"
echo ""
echo "1. Review test outputs for vulnerabilities discovered"
echo "2. Check CTFd logs: docker compose logs ctfd | grep -i 'security\|warning\|error'"
echo "3. Analyze database integrity: docker compose exec db mysql -u ctfd -pctfd ctfd"
echo "4. Generate security hardening report based on findings"
echo ""
echo "================================================================================"
