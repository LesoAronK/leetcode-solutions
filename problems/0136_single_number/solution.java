class Solution {
    public int singleNumber(int[] nums) {
        int n=nums.length;
        int XOR_val=0;
        for(int i=0;i<n;i++){
            XOR_val=XOR_val^nums[i];
        }
        return XOR_val;
        
    }
}