class Solution {
    public int missingNumber(int[] nums) {
        int len=nums.length;
        int n=len;
        int ap_sum=(n*(n+1))/2;
        int sum_arr=0;
        for(int i=0;i<n;i++){
            sum_arr=sum_arr+nums[i];
        }
        return ap_sum-sum_arr;
        
    }
}